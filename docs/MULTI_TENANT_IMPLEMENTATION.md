# Multi-Tenant Architecture Implementation

## Overview

LightRAG now supports **true multi-tenancy** where a single container can serve multiple tenants and projects simultaneously. Each tenant/project combination gets its own isolated LightRAG instance with separate storage, ensuring complete data isolation.

## Architecture

### Key Components

1. **LightRAGInstanceManager** (`lightrag/api/instance_manager.py`)
   - Manages a pool of LightRAG instances
   - One instance per `(tenant_id, project_id)` combination
   - Implements LRU caching with configurable limits
   - Automatic cleanup of inactive instances

2. **HTTP Headers**
   - `X-Tenant-ID`: Identifies the tenant making the request
   - `X-Project-ID`: Identifies the project within the tenant
   - Falls back to `DEFAULT_TENANT_ID` and `DEFAULT_PROJECT_ID` from environment if not provided

3. **Database Isolation**
   - All PostgreSQL tables include `tenant_id` and `project_id` columns
   - Primary keys: `(tenant_id, project_id, workspace, id)`
   - All queries filter by these columns
   - Graph names: `{tenant_id}_{project_id}_{workspace}_{namespace}`

### Request Flow

```
HTTP Request
  ↓
  Headers: X-Tenant-ID, X-Project-ID
  ↓
  get_rag_instance(request)
  ↓
  LightRAGInstanceManager.get_instance(tenant_id, project_id)
  ↓
  LightRAG instance (cached or new)
  ↓
  Storage operations (with tenant_id/project_id filters)
```

## Configuration

### Environment Variables

```bash
# Default tenant/project when headers are not provided
DEFAULT_TENANT_ID=default
DEFAULT_PROJECT_ID=default

# Instance pool configuration
LIGHTRAG_MAX_INSTANCES=100          # Maximum cached instances
LIGHTRAG_INSTANCE_TTL_MINUTES=60    # Inactive instance TTL
```

### Instance Manager Settings

- **max_instances**: Maximum number of cached instances (LRU eviction when exceeded)
- **ttl_minutes**: Inactive instances are removed after this period
- Instances are created lazily on first request
- Automatic cleanup of expired instances

## Usage

### Making API Requests

Include tenant and project headers in all API calls:

```bash
# Insert document for tenant1/project1
curl -X POST http://localhost:9621/documents/insert \
  -H "X-Tenant-ID: tenant1" \
  -H "X-Project-ID: project1" \
  -F "file=@document.txt"

# Query for tenant1/project2
curl -X POST http://localhost:9621/query/data \
  -H "X-Tenant-ID: tenant1" \
  -H "X-Project-ID: project2" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "mode": "hybrid"}'

# Different tenant gets completely isolated data
curl -X POST http://localhost:9621/query/data \
  -H "X-Tenant-ID: tenant2" \
  -H "X-Project-ID: project1" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "mode": "hybrid"}'
```

### Monitoring

Check instance manager statistics via `/health` endpoint:

```bash
curl http://localhost:9621/health
```

Response includes:
```json
{
  "instance_manager": {
    "active_instances": 3,
    "max_instances": 100,
    "ttl_minutes": 60,
    "instances": [
      {
        "tenant_id": "tenant1",
        "project_id": "project1",
        "last_access": "2025-01-15T10:30:00"
      }
    ]
  }
}
```

## Data Isolation

### Storage Level

All storage classes automatically filter by `tenant_id` and `project_id`:

- **PGKVStorage**: Key-value storage (LLM cache, chunks, documents, entities, relations)
- **PGVectorStorage**: Vector embeddings (entities, relations, chunks)
- **PGDocStatusStorage**: Document processing status
- **PGGraphStorage**: Apache AGE graph storage

### Examples

```python
# Tenant1/Project1 data
INSERT INTO lightrag_chunks (tenant_id, project_id, workspace, id, data)
VALUES ('tenant1', 'project1', 'default', 'chunk1', '...');

# Tenant1/Project2 data (different project, same tenant)
INSERT INTO lightrag_chunks (tenant_id, project_id, workspace, id, data)
VALUES ('tenant1', 'project2', 'default', 'chunk1', '...');

# Tenant2/Project1 data (different tenant)
INSERT INTO lightrag_chunks (tenant_id, project_id, workspace, id, data)
VALUES ('tenant2', 'project1', 'default', 'chunk1', '...');
```

All queries include `WHERE tenant_id = $1 AND project_id = $2`:

```python
# Get chunks for specific tenant/project
SELECT * FROM lightrag_chunks
WHERE tenant_id = 'tenant1'
  AND project_id = 'project1'
  AND workspace = 'default';
```

### Graph Isolation

Graph names include tenant and project:

```python
graph_name = f"{tenant_id}_{project_id}_{workspace}_{namespace}"
# Example: "tenant1_project1_default_entities"
```

This ensures complete graph isolation in Apache AGE.

## Implementation Details

### Router Changes

All routers now accept a `get_rag_instance` function instead of a `rag` instance:

```python
# Old (static instance)
def create_document_routes(rag: LightRAG, ...):
    @router.post("/upload")
    async def upload(file: UploadFile):
        await rag.insert(...)  # Always uses same instance

# New (dynamic instance per request)
def create_document_routes(get_rag_instance: Callable, ...):
    @router.post("/upload")
    async def upload(request: Request, file: UploadFile):
        rag = await get_rag_instance(request)  # Gets correct instance
        await rag.insert(...)
```

### Instance Lifecycle

1. **Creation**: First request for a `(tenant_id, project_id)` creates new instance
2. **Caching**: Instance is cached in LRU OrderedDict
3. **Reuse**: Subsequent requests reuse the cached instance
4. **TTL**: Last access time is tracked, expired instances are removed
5. **LRU**: When max_instances is reached, least recently used instance is evicted
6. **Cleanup**: Instances are properly finalized before removal

### Storage Initialization

Each LightRAG instance initializes its own storage connections when first accessed. This happens lazily to optimize resource usage.

## Migration from Neo4j

This implementation completely replaces Neo4j with PostgreSQL + Apache AGE:

- ✅ Removed Neo4j dependency
- ✅ All graph operations use Apache AGE (Cypher queries)
- ✅ Vector operations use pgvector
- ✅ Document storage uses JSONB
- ✅ Complete multi-tenant isolation at database level

## Performance Considerations

### Instance Pool Size

- **Too small**: Frequent instance creation/eviction, slower response times
- **Too large**: High memory usage, potential resource exhaustion
- **Recommended**: Start with 100, adjust based on:
  - Number of active tenants/projects
  - Memory available
  - Request patterns

### TTL Configuration

- **Short TTL (< 30 min)**: More frequent cleanup, lower memory usage, more instance recreation
- **Long TTL (> 120 min)**: Better performance for sporadic access, higher memory usage
- **Recommended**: 60 minutes for balanced approach

### Connection Pooling

PostgreSQL connection pooling is handled by the storage implementations. Each instance maintains its own connections, so monitor total connections:

```
Max DB Connections >= (max_instances × connections_per_instance)
```

## Testing Multi-Tenancy

### Test Isolation

```bash
# Create document for tenant1
curl -X POST http://localhost:9621/documents/upload \
  -H "X-Tenant-ID: tenant1" \
  -H "X-Project-ID: project1" \
  -F "file=@test1.txt"

# Verify tenant2 cannot see it
curl -X GET http://localhost:9621/documents/list \
  -H "X-Tenant-ID: tenant2" \
  -H "X-Project-ID: project1"
# Should return empty or different documents
```

### Database Verification

```sql
-- Check data distribution
SELECT tenant_id, project_id, COUNT(*)
FROM lightrag_chunks
GROUP BY tenant_id, project_id;

-- Verify isolation
SELECT * FROM lightrag_chunks
WHERE tenant_id = 'tenant1' AND project_id = 'project1';
```

## Security Considerations

1. **Header Validation**: Currently accepts any tenant/project ID from headers
   - Consider adding authentication/authorization
   - Validate tenant/project access rights
   - Map authenticated users to allowed tenant/project combinations

2. **Resource Limits**: Set appropriate limits
   - `LIGHTRAG_MAX_INSTANCES` prevents memory exhaustion
   - Consider per-tenant rate limiting
   - Monitor storage usage per tenant

3. **Data Isolation**: Enforced at database level
   - Primary keys include tenant_id/project_id
   - All queries filter by these columns
   - PostgreSQL row-level security could add additional layer

## Troubleshooting

### High Memory Usage

- Reduce `LIGHTRAG_MAX_INSTANCES`
- Decrease `LIGHTRAG_INSTANCE_TTL_MINUTES`
- Monitor instance manager stats via `/health`

### Slow First Request

- First request per tenant/project creates new instance
- Subsequent requests are faster (cached)
- Consider pre-warming frequently used instances

### Connection Pool Exhausted

- Check PostgreSQL `max_connections`
- Reduce `LIGHTRAG_MAX_INSTANCES`
- Monitor active instances via `/health`

## Future Enhancements

1. **Authentication Integration**: Map users to tenant/project access
2. **Resource Quotas**: Per-tenant storage/compute limits
3. **Admin API**: Create/manage tenants programmatically
4. **Metrics**: Per-tenant usage statistics
5. **Sharding**: Distribute tenants across multiple databases
