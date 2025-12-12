# Sistema Multi-Tenant Completo - Guia de Implementação

## Visão Geral

O LightRAG agora possui um **sistema multi-tenant completo** com:

✅ **Autenticação JWT** (login no painel web)  
✅ **API Keys** (acesso programático)  
✅ **Configurações de LLM por projeto** (sem dependência do `.env`)  
✅ **Gerenciamento de projetos e colaboradores**  
✅ **Isolamento completo de dados** (tenant → project → workspace)  

## Arquitetura Final

```
┌─────────────────────────────────────────────────────────────────┐
│                     LightRAG Multi-Tenant                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐      ┌──────────────────┐                 │
│  │   Web Panel     │──────│  JWT Auth        │                 │
│  │   (React UI)    │      │  (1h access)     │                 │
│  └─────────────────┘      └──────────────────┘                 │
│           │                                                      │
│           │                                                      │
│  ┌─────────────────┐      ┌──────────────────┐                 │
│  │  External Apps  │──────│  API Keys        │                 │
│  │  (Scripts/Bots) │      │  (persistent)    │                 │
│  └─────────────────┘      └──────────────────┘                 │
│           │                        │                            │
│           └────────────┬───────────┘                            │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  Auth Middleware       │                           │
│            │  (JWT or API Key)      │                           │
│            └────────────────────────┘                           │
│                        │                                        │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  get_rag_instance()    │                           │
│            │  Dependency            │                           │
│            └────────────────────────┘                           │
│                        │                                        │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  Instance Manager      │                           │
│            │  (LRU Cache)           │                           │
│            └────────────────────────┘                           │
│                        │                                        │
│                        ├─────── Get LLM Config from DB          │
│                        │                                        │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  LLMConfigService      │                           │
│            │  (fetch + decrypt)     │                           │
│            └────────────────────────┘                           │
│                        │                                        │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  LLM Factory           │                           │
│            │  (create LLM func)     │                           │
│            └────────────────────────┘                           │
│                        │                                        │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  LightRAG Instance     │                           │
│            │  (tenant/project)      │                           │
│            └────────────────────────┘                           │
│                        │                                        │
│                        ▼                                        │
│            ┌────────────────────────┐                           │
│            │  PostgreSQL + AGE      │                           │
│            │  (isolated by IDs)     │                           │
│            └────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Componentes Implementados

### 1. Database Schema (PostgreSQL + Apache AGE)

**Scripts de Inicialização**:
- `init-db.sql` - AGE extension + pgcrypto + permissões
- `init-auth-tables.sql` - 7 tabelas de autenticação
- `init-api-keys-table.sql` - Tabela de API keys
- `init-llm-configs-table.sql` - **NOVO**: Configurações de LLM

**Tabelas**:
```sql
-- Autenticação
lightrag_users
lightrag_tenants
lightrag_projects
lightrag_project_members
lightrag_invitations
lightrag_refresh_tokens
lightrag_audit_log

-- API Keys
lightrag_api_keys

-- LLM Configurations (NOVO)
lightrag_llm_configs
```

### 2. Backend Services

**AuthService** (`lightrag/api/services/auth_service.py`)
- Registro de usuários
- Login/logout
- Verificação de email
- Reset de senha
- Refresh de tokens JWT

**ProjectService** (`lightrag/api/services/project_service.py`)
- Criar tenants e projetos
- Gerenciar membros
- Sistema de convites
- Controle de permissões (OWNER/ADMIN/MEMBER/VIEWER)

**APIKeyService** (`lightrag/api/services/api_key_service.py`)
- Gerar API keys (`lrag_xxx`)
- Validar keys com bcrypt
- Scopes: query, insert, delete, admin
- Revogação e expiração

**LLMConfigService** (`lightrag/api/services/llm_config_service.py`) **NOVO**
- CRUD de configurações de LLM
- Criptografia de API keys com pgcrypto
- Suporte a 8 providers:
  - OpenAI, Azure OpenAI, Ollama
  - Anthropic, Gemini, Bedrock
  - HuggingFace, OpenAI-compatible
- Configurações de embedding separadas

### 3. API Routes

**Authentication** (`/auth`)
- POST `/auth/register` - Registrar usuário
- POST `/auth/login` - Login (retorna JWT)
- GET `/auth/verify-email` - Verificar email
- POST `/auth/password-reset/request` - Solicitar reset
- POST `/auth/password-reset/confirm` - Confirmar reset
- POST `/auth/refresh` - Refresh access token
- POST `/auth/logout` - Logout

**Projects** (`/projects`)
- POST `/projects/tenants` - Criar tenant
- POST `/projects` - Criar projeto
- GET `/projects` - Listar projetos do usuário
- POST `/projects/{id}/invite` - Convidar membro
- POST `/projects/invitations/{token}/accept` - Aceitar convite
- PUT `/projects/{id}/members/{user_id}` - Atualizar role

**API Keys** (`/api-keys`)
- POST `/api-keys` - Criar API key
- GET `/api-keys` - Listar suas keys
- DELETE `/api-keys/{id}` - Revogar key

**LLM Configs** (`/llm-configs`) **NOVO**
- POST `/llm-configs` - Criar configuração de LLM
- GET `/llm-configs/project/{id}` - Listar configs do projeto
- GET `/llm-configs/{id}` - Ver configuração
- PUT `/llm-configs/{id}` - Atualizar configuração
- DELETE `/llm-configs/{id}` - Deletar configuração

### 4. Instance Manager (Atualizado)

**Arquivo**: `lightrag/api/instance_manager.py`

**Mudanças**:
- Aceita `llm_config_service` no construtor
- Busca configuração de LLM do banco ao criar instância
- Usa `LLM Factory` para criar funções LLM apropriadas
- Suporta fallback para `.env` se multi-tenant desabilitado

```python
# Antes (usava .env)
instance = LightRAG(**base_config)

# Agora (busca do banco)
llm_config = await llm_config_service.get_default_config(project_id)
llm_func = create_llm_from_config(llm_config)
instance = LightRAG(**base_config, llm_model_func=llm_func)
```

### 5. LLM Factory (Novo)

**Arquivo**: `lightrag/api/llm_factory.py`

**Funções**:
- `create_openai_llm_func()` - OpenAI
- `create_ollama_llm_func()` - Ollama (local)
- `create_azure_openai_llm_func()` - Azure OpenAI
- `create_openai_compatible_llm_func()` - APIs compatíveis
- `create_embedding_func()` - Embeddings por provider
- `create_llm_from_config()` - Factory principal
- `create_embedding_from_config()` - Factory de embeddings

### 6. Auth Middleware (Atualizado)

**Arquivo**: `lightrag/api/middleware/auth_middleware.py`

**Mudanças**:
- Detecta automaticamente JWT vs API Key
- Valida API keys com `APIKeyService`
- Popula `request.state` com contexto apropriado:
  - JWT: `user_id`, `user_email`, `auth_type="jwt"`
  - API Key: `user_id`, `tenant_id`, `project_id`, `scopes`, `auth_type="api_key"`

### 7. Server Integration

**Arquivo**: `lightrag/api/lightrag_server.py`

**Lifespan atualizado**:
```python
async def lifespan(app: FastAPI):
    # Criar pool de conexões PostgreSQL
    db_pool = await asyncpg.create_pool(...)
    
    # Inicializar serviços
    auth_service = AuthService(db_pool)
    project_service = ProjectService(db_pool)
    api_key_service = APIKeyService(db_pool)
    llm_config_service = LLMConfigService(db_pool)
    
    # Passar llm_config_service para instance_manager
    instance_manager.llm_config_service = llm_config_service
    
    # Armazenar em app.state
    app.state.auth_service = auth_service
    # ... outros services
    
    yield
    
    # Cleanup
    await instance_manager.shutdown()
    await db_pool.close()
```

**Middlewares e routers**:
```python
# Adicionar middleware de autenticação
app.add_middleware(AuthMiddleware, auth_service, api_key_service)

# Adicionar routers multi-tenant
app.include_router(auth_router, prefix="/auth")
app.include_router(project_router, prefix="/projects")
app.include_router(api_key_router, prefix="/api-keys")
app.include_router(llm_config_router, prefix="/llm-configs")
```

## Variáveis de Ambiente

**Arquivo**: `.env`

```bash
#####################################
### Multi-Tenant Configuration
#####################################
LIGHTRAG_MULTI_TENANT=true  # ENABLE MULTI-TENANT MODE

DEFAULT_TENANT_ID=default
DEFAULT_PROJECT_ID=default
LIGHTRAG_MAX_INSTANCES=100
LIGHTRAG_INSTANCE_TTL_MINUTES=60

#####################################
### PostgreSQL Configuration
#####################################
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your-secure-password

#####################################
### JWT Configuration
#####################################
JWT_SECRET_KEY=change-this-to-secure-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

#####################################
### LLM Config Encryption
#####################################
LLM_CONFIG_ENCRYPTION_KEY=change-this-to-secure-key-min-32-chars

#####################################
### Email Configuration
#####################################
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=LightRAG
```

## Fluxo de Uso Completo

### 1. Setup Inicial

```bash
# 1. Copiar environment variables
cp env.example .env

# 2. Editar .env
# - Definir LIGHTRAG_MULTI_TENANT=true
# - Configurar PostgreSQL
# - Gerar JWT_SECRET_KEY: openssl rand -base64 32
# - Gerar LLM_CONFIG_ENCRYPTION_KEY: openssl rand -base64 32
# - Configurar SMTP

# 3. Iniciar containers
docker-compose up -d

# 4. Verificar logs
docker-compose logs -f lightrag
```

### 2. Registrar Primeiro Usuário

```bash
curl -X POST http://localhost:9621/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePass123!",
    "full_name": "Admin User",
    "phone": "+5511999999999"
  }'

# Response: {"message": "Registration successful. Please check your email..."}
```

### 3. Fazer Login

```bash
curl -X POST http://localhost:9621/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePass123!"
  }'

# Response:
# {
#   "access_token": "eyJhbGc...",
#   "refresh_token": "eyJhbGc...",
#   "token_type": "bearer",
#   "expires_in": 3600
# }

# Salvar o access_token
JWT_TOKEN="eyJhbGc..."
```

### 4. Criar Tenant e Projeto

```bash
# Criar tenant
curl -X POST http://localhost:9621/projects/tenants \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company",
    "description": "Company knowledge base"
  }'

# Response: {"id": "tenant-uuid", "name": "My Company", ...}
TENANT_ID="tenant-uuid"

# Criar projeto
curl -X POST http://localhost:9621/projects \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "'$TENANT_ID'",
    "name": "Documentation",
    "description": "Product documentation RAG"
  }'

# Response: {"id": "project-uuid", ...}
PROJECT_ID="project-uuid"
```

### 5. Configurar LLM (OpenAI)

```bash
curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'$PROJECT_ID'",
    "name": "Production OpenAI",
    "provider": "openai",
    "api_key": "sk-your-openai-key",
    "model_name": "gpt-4-turbo-preview",
    "temperature": 0.7,
    "max_tokens": 4000,
    "is_default": true
  }'

# Response:
# {
#   "id": "config-uuid",
#   "name": "Production OpenAI",
#   "provider": "openai",
#   "has_api_key": true,  # Key nunca exposta
#   "is_default": true
# }
```

### 6. Criar API Key para Acesso Programático

```bash
curl -X POST http://localhost:9621/api-keys \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'$PROJECT_ID'",
    "name": "Production API",
    "scopes": ["query", "insert"]
  }'

# Response:
# {
#   "id": "key-uuid",
#   "key": "lrag_j8kx9mq2n4p6r8t1v3w5y7z0a2c4e",  # ⚠️ COPIE AGORA!
#   "key_prefix": "lrag_j8kx9m...",
#   "scopes": ["query", "insert"]
# }

API_KEY="lrag_j8kx9mq2n4p6r8t1v3w5y7z0a2c4e"
```

### 7. Inserir Documentos

```bash
curl -X POST http://localhost:9621/documents \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "RAG is Retrieval-Augmented Generation...",
    "metadata": {"source": "docs", "section": "introduction"}
  }'

# Ou via headers (JWT)
curl -X POST http://localhost:9621/documents \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Tenant-ID: '$TENANT_ID'" \
  -H "X-Project-ID: '$PROJECT_ID'" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "..."
  }'
```

### 8. Fazer Queries

```bash
# Com API Key (tenant/project automático)
curl -X POST http://localhost:9621/query/data \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RAG?",
    "mode": "hybrid"
  }'

# Com JWT (precisa headers)
curl -X POST http://localhost:9621/query/data \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Tenant-ID: '$TENANT_ID'" \
  -H "X-Project-ID: '$PROJECT_ID'" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RAG?",
    "mode": "hybrid"
  }'
```

## Providers de LLM Suportados

### OpenAI
```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "model_name": "gpt-4-turbo-preview",
  "base_url": null
}
```

### Azure OpenAI
```json
{
  "provider": "azure_openai",
  "api_key": "your-azure-key",
  "model_name": "gpt-4",
  "base_url": "https://your-resource.openai.azure.com",
  "additional_config": {
    "api_version": "2023-05-15",
    "deployment_name": "gpt-4-deployment"
  }
}
```

### Ollama (Local)
```json
{
  "provider": "ollama",
  "model_name": "llama2",
  "base_url": "http://localhost:11434"
}
```

### Anthropic Claude
```json
{
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model_name": "claude-3-opus-20240229"
}
```

## Segurança

### Criptografia de API Keys
- **LLM API Keys**: Criptografadas com `pgp_sym_encrypt()` no PostgreSQL
- **Chave de Criptografia**: `LLM_CONFIG_ENCRYPTION_KEY` (env var)
- **Descriptografia**: Apenas no `instance_manager` ao criar instância
- **Nunca exposta**: Responses só retornam `has_api_key: boolean`

### Autenticação Dual
- **JWT**: Para painel web (expira em 1h)
- **API Keys**: Para acesso programático (persistente)
- **Middleware**: Detecta automaticamente qual usar

### Isolamento de Dados
- **Database**: Todas as queries filtradas por `tenant_id` + `project_id`
- **Instance Manager**: Uma instância LightRAG por (tenant, project)
- **Permissões**: Verificadas em cada request via `ProjectService`

## Troubleshooting

### "No LLM configuration found for project"
```bash
# Criar configuração de LLM
curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"project_id": "...", "provider": "openai", ...}'
```

### "Authentication required"
```bash
# Verificar se token é válido
curl -X GET http://localhost:9621/auth/me \
  -H "Authorization: Bearer $JWT_TOKEN"

# Se expirado, fazer refresh
curl -X POST http://localhost:9621/auth/refresh \
  -d '{"refresh_token": "..."}'
```

### "API key requires 'query' scope"
```bash
# Verificar scopes da API key
curl -X GET http://localhost:9621/api-keys \
  -H "Authorization: Bearer $JWT_TOKEN"

# Criar nova key com scopes corretos
curl -X POST http://localhost:9621/api-keys \
  -d '{"scopes": ["query", "insert", "delete"]}'
```

## Documentação Adicional

- [Multi-Tenant Implementation](./MULTI_TENANT_IMPLEMENTATION.md)
- [Authentication System](./AUTH_SYSTEM_COMPLETE.md)
- [API Keys Integration](./API_KEYS_INTEGRATION.md)
- [LLM Configuration System](./LLM_CONFIG_SYSTEM.md)
- [Router Migration Guide](./ROUTER_MIGRATION_TODO.md)

## Status da Implementação

✅ **Completo**:
- PostgreSQL + Apache AGE setup
- Schemas de banco (11 LightRAG + 7 auth + 1 API keys + 1 LLM configs)
- Todos os services (Auth, Project, APIKey, LLMConfig)
- Todos os routers (auth, projects, api-keys, llm-configs)
- Auth middleware (JWT + API Key)
- Instance manager com LLM configs do banco
- LLM factory para 8 providers
- Integração completa no lightrag_server.py
- Documentação completa

⏳ **Próximos Passos**:
- Frontend UI (Login, Projects, API Keys, LLM Configs)
- Email service implementation
- End-to-end testing
- Migration tool (.env → database configs)
