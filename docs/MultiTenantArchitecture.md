# LightRAG Multi-Tenant Architecture

## Overview

LightRAG now supports a comprehensive multi-tenant architecture using PostgreSQL with Apache AGE for graph storage, completely replacing Neo4j. This architecture enables data isolation at three levels:

1. **Tenant (Company/Organization)** - `tenant_id`
2. **Project (within Tenant)** - `project_id`
3. **Workspace (Environment)** - `workspace` (dev, staging, prod)

## Architecture Benefits

### Why PostgreSQL + Apache AGE?

- ✅ **Single Database**: All data (documents, vectors, graphs) in one PostgreSQL instance
- ✅ **Cost Effective**: No need for separate Neo4j infrastructure
- ✅ **Native Graph Support**: Apache AGE provides Cypher query support
- ✅ **Multi-Tenant Ready**: Built-in support for data isolation
- ✅ **Scalability**: PostgreSQL proven scaling capabilities
- ✅ **ACID Compliance**: Strong consistency guarantees

### Data Isolation Model

```
┌─────────────────────────────────────────────────────┐
│ Database: lightrag                                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Tenant: company_a                                  │
│  ├─ Project: project_alpha                          │
│  │  ├─ Workspace: development                       │
│  │  ├─ Workspace: staging                           │
│  │  └─ Workspace: production                        │
│  └─ Project: project_beta                           │
│     └─ Workspace: production                        │
│                                                      │
│  Tenant: company_b                                  │
│  └─ Project: project_gamma                          │
│     ├─ Workspace: development                       │
│     └─ Workspace: production                        │
└─────────────────────────────────────────────────────┘
```

## Database Schema

All tables now include:
- `tenant_id VARCHAR(255)` - Organization identifier
- `project_id VARCHAR(255)` - Project identifier  
- `workspace VARCHAR(255)` - Environment identifier

Primary keys changed from `(workspace, id)` to `(tenant_id, project_id, workspace, id)`

### AGE Graph Naming Convention

Graphs are isolated using naming: `{tenant_id}_{project_id}_{workspace}_{namespace}`

Example: `company_a_project_alpha_production_entities`

## API Usage

### HTTP Headers

Multi-tenant requests use custom headers:

```http
POST /query HTTP/1.1
Host: localhost:8020
Content-Type: application/json
X-Tenant-ID: company_a
X-Project-ID: project_alpha  
X-Workspace: production

{
  "query": "What is the status?",
  "mode": "hybrid"
}
```

### Header Defaults

If headers are not provided, defaults are used:
- `X-Tenant-ID`: `default` (or `DEFAULT_TENANT_ID` env var)
- `X-Project-ID`: `default` (or `DEFAULT_PROJECT_ID` env var)
- `X-Workspace`: `default` (or server `--workspace` arg)

### Example with cURL

```bash
curl -X POST http://localhost:8020/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: acme_corp" \
  -H "X-Project-ID: sales_insights" \
  -H "X-Workspace: production" \
  -d '{
    "query": "Show me recent deals",
    "mode": "hybrid"
  }'
```

### Example with Python

```python
import requests

url = "http://localhost:8020/query"
headers = {
    "Content-Type": "application/json",
    "X-Tenant-ID": "acme_corp",
    "X-Project-ID": "sales_insights", 
    "X-Workspace": "production"
}
data = {
    "query": "Show me recent deals",
    "mode": "hybrid"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

## Configuration

### Environment Variables

```bash
# PostgreSQL Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=lightrag

# Multi-Tenant Defaults (optional)
DEFAULT_TENANT_ID=default
DEFAULT_PROJECT_ID=default
DEFAULT_WORKSPACE=default

# Storage Configuration (use PostgreSQL for everything)
LIGHTRAG_KV_STORAGE=PGKVStorage
LIGHTRAG_DOC_STATUS_STORAGE=PGDocStatusStorage
LIGHTRAG_GRAPH_STORAGE=PGGraphStorage
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage
```

### Python Code

```python
from lightrag import LightRAG

# Initialize with tenant/project context
rag = LightRAG(
    working_dir="./rag_storage",
    llm_model_func=your_llm_function,
    tenant_id="acme_corp",
    project_id="sales_insights",
    workspace="production"
)

# Insert documents
await rag.ainsert("Your document text here")

# Query
result = await rag.aquery("What is this about?", mode="hybrid")
```

## Migration Guide

See [MultiTenantMigration.md](./MultiTenantMigration.md) for detailed migration steps.

### Quick Migration

1. **Install Apache AGE Extension**
   ```sql
   CREATE EXTENSION IF NOT EXISTS age;
   LOAD 'age';
   SET search_path = ag_catalog, "$user", public;
   ```

2. **Run Migration Script**
   ```bash
   psql -U lightrag -d lightrag -f migrations/001_add_multi_tenant_support.sql
   ```

3. **Update Configuration**
   - Remove Neo4j environment variables
   - Set `LIGHTRAG_GRAPH_STORAGE=PGGraphStorage`
   - Configure tenant/project defaults

4. **Restart Application**
   ```bash
   lightrag-server --workspace production
   ```

## Performance Considerations

### Indexes

The migration creates composite indexes for common query patterns:

```sql
CREATE INDEX idx_doc_full_tenant_project_workspace 
  ON LIGHTRAG_DOC_FULL(tenant_id, project_id, workspace);
```

### Query Optimization

- Always filter by `tenant_id` and `project_id` first
- Use workspace filtering for environment isolation
- AGE graph queries are optimized for tenant-specific graphs

### Connection Pooling

Configure connection pool size based on concurrent tenants:

```bash
POSTGRES_MAX_CONNECTIONS=50  # Adjust based on load
```

## Security

### Data Isolation

- Row-Level Security (RLS) can be enabled for additional protection
- Each tenant's data is physically separated by primary key
- Graphs are isolated by naming convention

### Access Control

```sql
-- Example: Create role for a specific tenant
CREATE ROLE tenant_acme_corp;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public 
  TO tenant_acme_corp;

-- Add row-level security policy
CREATE POLICY tenant_isolation ON LIGHTRAG_DOC_FULL
  FOR ALL TO tenant_acme_corp
  USING (tenant_id = current_setting('app.tenant_id'));
```

## Monitoring

### Query Performance

```sql
-- Check tenant data distribution
SELECT tenant_id, project_id, workspace, 
       COUNT(*) as doc_count
FROM LIGHTRAG_DOC_STATUS
GROUP BY tenant_id, project_id, workspace
ORDER BY doc_count DESC;

-- Check graph sizes
SELECT schemaname, 
       tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname LIKE '%_%_%_%'  -- AGE graphs
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Active Connections

```sql
-- Monitor connections by application
SELECT datname, usename, application_name, 
       COUNT(*) as connection_count
FROM pg_stat_activity
WHERE datname = 'lightrag'
GROUP BY datname, usename, application_name;
```

## Troubleshooting

### Common Issues

**Issue**: Graph queries are slow
- **Solution**: Ensure AGE indexes are created, run `ANALYZE` on graph tables

**Issue**: Connection pool exhausted  
- **Solution**: Increase `POSTGRES_MAX_CONNECTIONS` or reduce `MAX_ASYNC`

**Issue**: Cannot find graph
- **Solution**: Check graph naming convention matches `{tenant}_{project}_{workspace}_{namespace}`

### Debug Logging

Enable detailed logging:

```bash
LOG_LEVEL=DEBUG
VERBOSE=True
```

Check logs for tenant/project context:
```
[tenant=acme_corp][project=sales][workspace=prod] PostgreSQL Graph initialized: graph_name='acme_corp_sales_prod_entities'
```

## Best Practices

1. **Use Meaningful IDs**: Choose descriptive tenant and project IDs
2. **Consistent Naming**: Use lowercase with underscores (e.g., `acme_corp`)
3. **Workspace Strategy**: Maintain separate workspaces for dev/staging/prod
4. **Regular Backups**: Backup PostgreSQL database with all tenant data
5. **Monitor Growth**: Track data growth per tenant for capacity planning
6. **Clean Old Data**: Implement data retention policies per tenant

## FAQ

**Q: Can I still use Neo4j?**  
A: Neo4j support has been removed in favor of PostgreSQL + AGE for simplified architecture.

**Q: How many tenants can the system support?**  
A: Theoretically unlimited. Performance depends on data volume per tenant and PostgreSQL configuration.

**Q: Can tenants have different LLM models?**  
A: Yes, LLM configuration can be customized per-request in the API.

**Q: Is the data truly isolated?**  
A: Yes, at the database level through composite primary keys and at the graph level through naming isolation.

**Q: Can I migrate between tenants?**  
A: Yes, use SQL to copy/move data between tenant_id/project_id combinations.

## Support

For issues or questions:
- GitHub Issues: https://github.com/cecon/LightRAG/issues
- Documentation: https://github.com/cecon/LightRAG/docs
