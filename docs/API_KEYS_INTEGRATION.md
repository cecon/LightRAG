# API Keys System - Integration Guide

## Overview

The LightRAG API now supports **dual authentication**:

1. **JWT Bearer Tokens** - For web panel login (short-lived, 1h access + 30d refresh)
2. **API Keys** - For programmatic access (persistent, revokable, like ChatGPT)

This separation ensures that:
- Web panel sessions expire regularly for security
- API integrations don't break due to token expiration
- API keys can be revoked without affecting panel access

## Architecture

### Database Schema

```sql
-- API Keys table (init-api-keys-table.sql)
CREATE TABLE lightrag_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES lightrag_tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES lightrag_projects(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,              -- User-friendly name (e.g., "Production API Key")
    key_prefix VARCHAR(12) NOT NULL,         -- First 12 chars for display (e.g., "lrag_abc...")
    key_hash TEXT NOT NULL,                  -- bcrypt hash of full key
    
    scopes JSONB NOT NULL DEFAULT '[]',      -- ["query", "insert", "delete", "admin"]
    
    expires_at TIMESTAMP,                    -- NULL = never expires
    last_used_at TIMESTAMP,                  -- Updated on each validation
    is_active BOOLEAN NOT NULL DEFAULT true,
    revoked_at TIMESTAMP,                    -- Soft delete timestamp
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### API Key Format

- **Format**: `lrag_<32 random alphanumeric characters>`
- **Example**: `lrag_j8kx9mq2n4p6r8t1v3w5y7z0a2c4e`
- **Prefix stored**: `lrag_j8kx9m...` (for display in UI)
- **Full key hashed**: bcrypt hash stored in database

### Scopes

| Scope | Description | Allowed Operations |
|-------|-------------|-------------------|
| `query` | Read operations | GET /query/*, search, retrieve |
| `insert` | Write operations | POST /documents, upsert |
| `delete` | Delete operations | DELETE /documents, purge |
| `admin` | Full access | All operations + member management |

Multiple scopes can be combined: `["query", "insert"]`

## Code Components

### 1. API Key Service
**File**: `lightrag/api/services/api_key_service.py`

```python
class APIKeyService:
    async def generate_api_key() -> Tuple[str, str, str]
        # Returns: (full_key, prefix, hash)
    
    async def create_api_key(...) -> APIKeyCreateResponse
        # Shows full key ONCE
    
    async def validate_api_key(key: str) -> Optional[Dict]
        # Returns {user_id, tenant_id, project_id, scopes}
    
    async def list_user_api_keys(...) -> List[APIKeyResponse]
        # Returns keys (without full key)
    
    async def revoke_api_key(...)
        # Soft delete
    
    async def delete_api_key(...)
        # Hard delete
```

### 2. API Key Routes
**File**: `lightrag/api/routers/api_key_routes.py`

```python
POST   /api-keys          # Create new API key
GET    /api-keys          # List user's API keys
DELETE /api-keys/{id}     # Revoke API key
DELETE /api-keys/{id}/permanent  # Delete permanently
```

### 3. Auth Middleware
**File**: `lightrag/api/middleware/auth_middleware.py`

Updated to detect and validate both:
- JWT tokens (existing behavior)
- API keys (new: starts with "lrag_")

```python
# Sets request.state.auth_type = "jwt" or "api_key"
# For API keys, also sets:
#   - request.state.tenant_id
#   - request.state.project_id
#   - request.state.scopes
```

### 4. get_rag_instance Dependency
**File**: `lightrag/api/lightrag_server.py`

Updated to support both auth types:

```python
async def get_rag_instance(request: Request) -> LightRAG:
    if auth_type == "api_key":
        # Use tenant/project from API key context
        tenant_id = request.state.tenant_id
        project_id = request.state.project_id
    else:
        # Use X-Tenant-ID and X-Project-ID headers (JWT auth)
        tenant_id = get_tenant_id_from_request(request)
        project_id = get_project_id_from_request(request)
```

## Integration Steps

### Step 1: Initialize Services in `lightrag_server.py`

Add to the `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database connection pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "lightrag"),
        user=os.getenv("POSTGRES_USER", "lightrag"),
        password=os.getenv("POSTGRES_PASSWORD", "lightrag"),
        min_size=5,
        max_size=20
    )
    
    # Initialize services
    auth_service = AuthService(db_pool)
    project_service = ProjectService(db_pool)
    api_key_service = APIKeyService(db_pool)
    
    # Store in app state
    app.state.db_pool = db_pool
    app.state.auth_service = auth_service
    app.state.project_service = project_service
    app.state.api_key_service = api_key_service
    app.state.instance_manager = instance_manager

    try:
        yield
    finally:
        await instance_manager.shutdown()
        await db_pool.close()
```

### Step 2: Add Auth Middleware

```python
# Import
from lightrag.api.middleware.auth_middleware import AuthMiddleware

# Add middleware
app.add_middleware(
    AuthMiddleware,
    auth_service=auth_service,
    api_key_service=api_key_service
)
```

### Step 3: Include Routes

```python
# Import
from lightrag.api.routers.auth_routes import router as auth_router
from lightrag.api.routers.project_routes import router as project_router
from lightrag.api.routers.api_key_routes import router as api_key_router

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(project_router, prefix="/projects", tags=["projects"])
app.include_router(api_key_router, prefix="/api-keys", tags=["api-keys"])
```

### Step 4: Environment Variables

Add to `.env`:

```bash
# Multi-tenant Configuration
LIGHTRAG_MULTI_TENANT=true
LIGHTRAG_DEFAULT_TENANT_ID=default-tenant
LIGHTRAG_DEFAULT_PROJECT_ID=default-project

# Database Configuration (PostgreSQL with AGE)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your-secure-password

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Email Configuration (for verification/invitations)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=LightRAG

# Instance Management
LIGHTRAG_MAX_INSTANCES=100
LIGHTRAG_INSTANCE_TTL_MINUTES=60
```

## Usage Examples

### Creating an API Key

**Step 1: Login to get JWT token**

```bash
curl -X POST http://localhost:9621/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'

# Response:
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

**Step 2: Create API key using JWT token**

```bash
curl -X POST http://localhost:9621/api-keys \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-uuid-here",
    "name": "Production API",
    "scopes": ["query", "insert"],
    "expires_at": null
  }'

# Response:
{
  "id": "key-uuid",
  "name": "Production API",
  "key": "lrag_j8kx9mq2n4p6r8t1v3w5y7z0a2c4e",  # ⚠️ SHOWN ONLY ONCE!
  "key_prefix": "lrag_j8kx9m...",
  "scopes": ["query", "insert"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

**⚠️ IMPORTANT**: Save the full `key` immediately! It won't be shown again.

### Using the API Key

**Query with API Key**

```bash
curl -X POST http://localhost:9621/query/data \
  -H "Authorization: Bearer lrag_j8kx9mq2n4p6r8t1v3w5y7z0a2c4e" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RAG?",
    "mode": "hybrid"
  }'
```

**Insert Document with API Key**

```bash
curl -X POST http://localhost:9621/documents \
  -H "Authorization: Bearer lrag_j8kx9mq2n4p6r8t1v3w5y7z0a2c4e" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "RAG is Retrieval-Augmented Generation...",
    "metadata": {"source": "docs"}
  }'
```

### Managing API Keys

**List your API keys**

```bash
curl -X GET http://localhost:9621/api-keys \
  -H "Authorization: Bearer eyJhbGc..."  # JWT token

# Response:
[
  {
    "id": "key-uuid-1",
    "name": "Production API",
    "key_prefix": "lrag_j8kx9m...",
    "scopes": ["query", "insert"],
    "last_used_at": "2024-01-15T14:20:00Z",
    "created_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "key-uuid-2",
    "name": "Development",
    "key_prefix": "lrag_abc123...",
    "scopes": ["query"],
    "last_used_at": null,
    "created_at": "2024-01-14T09:15:00Z"
  }
]
```

**Revoke API key**

```bash
curl -X DELETE http://localhost:9621/api-keys/key-uuid-1 \
  -H "Authorization: Bearer eyJhbGc..."  # JWT token

# Response:
{
  "message": "API key revoked successfully"
}
```

## Security Considerations

1. **Key Storage**: Full keys are hashed with bcrypt (same as passwords)
2. **One-time Display**: Full key shown only once at creation
3. **Prefix Storage**: Only first 12 chars stored for UI display
4. **Scope Validation**: Each request validates required scopes
5. **Expiration**: Keys can have optional expiration dates
6. **Soft Delete**: Revoked keys kept for audit logs
7. **Last Used Tracking**: Updates `last_used_at` on each validation

## Frontend Integration

### API Key Management Panel

```typescript
// Create API Key
const createApiKey = async (projectId: string, name: string, scopes: string[]) => {
  const response = await fetch('/api-keys', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ project_id: projectId, name, scopes })
  });
  
  const data = await response.json();
  
  // ⚠️ CRITICAL: Show full key to user and warn to copy it
  alert(`API Key created: ${data.key}\n\nCopy this now - you won't see it again!`);
};

// List API Keys
const listApiKeys = async () => {
  const response = await fetch('/api-keys', {
    headers: { 'Authorization': `Bearer ${jwtToken}` }
  });
  return await response.json();
};

// Revoke API Key
const revokeApiKey = async (keyId: string) => {
  await fetch(`/api-keys/${keyId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${jwtToken}` }
  });
};
```

## Testing

### Unit Tests

```python
# tests/test_api_key_service.py
async def test_generate_api_key():
    full_key, prefix, hash = await APIKeyService.generate_api_key()
    assert full_key.startswith("lrag_")
    assert len(full_key) == 37  # "lrag_" + 32 chars
    assert prefix == full_key[:12]
    assert bcrypt.checkpw(full_key.encode(), hash.encode())

async def test_validate_api_key():
    # Create key
    response = await api_key_service.create_api_key(...)
    
    # Validate key
    context = await api_key_service.validate_api_key(response.key)
    assert context["user_id"] == user_id
    assert "query" in context["scopes"]
```

### Integration Tests

```bash
# Test full flow
pytest tests/test_api_key_flow.py -v

# Test with real PostgreSQL
LIGHTRAG_RUN_INTEGRATION=true pytest tests/test_api_key_integration.py
```

## Migration Notes

### Existing Users

- Existing JWT-based authentication continues to work
- No breaking changes to existing API endpoints
- API keys are opt-in feature

### Backwards Compatibility

- All existing routes support both JWT and API key authentication
- `get_rag_instance` automatically detects auth type
- Headers (X-Tenant-ID, X-Project-ID) still work with JWT auth

## Next Steps

1. ✅ API Key Service implemented
2. ✅ API Key Routes created
3. ✅ Auth Middleware updated
4. ✅ get_rag_instance updated
5. ⏳ Integrate services into lightrag_server.py
6. ⏳ Frontend UI for API key management
7. ⏳ Update existing router migrations
8. ⏳ Email service for invitations
9. ⏳ End-to-end testing

## References

- [API Keys Schema](../k8s-deploy/databases/init-api-keys-table.sql)
- [API Key Service](../lightrag/api/services/api_key_service.py)
- [API Key Routes](../lightrag/api/routers/api_key_routes.py)
- [Auth Middleware](../lightrag/api/middleware/auth_middleware.py)
- [Multi-Tenant Implementation](./MULTI_TENANT_IMPLEMENTATION.md)
- [Auth System Complete](./AUTH_SYSTEM_COMPLETE.md)
