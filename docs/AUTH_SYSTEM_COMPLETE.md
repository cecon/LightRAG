# Sistema de Autenticação e Multi-Tenant - LightRAG

## Visão Geral

Sistema completo de autenticação de usuários integrado com arquitetura multi-tenant, permitindo que múltiplos usuários colaborem em projetos isolados.

## Arquitetura Implementada

### 1. Banco de Dados (PostgreSQL)

#### Tabelas Criadas:
- **lightrag_users**: Usuários do sistema (email, senha hash, nome, telefone)
- **lightrag_tenants**: Organizações/empresas
- **lightrag_projects**: Projetos dentro de tenants
- **lightrag_project_members**: Membros de projetos com roles
- **lightrag_invitations**: Convites pendentes para projetos
- **lightrag_refresh_tokens**: Tokens de refresh JWT
- **lightrag_audit_log**: Log de auditoria

#### Hierarquia:
```
User (usuário)
  ↓
Tenant (empresa/organização)
  ↓
Project (projeto)
  ↓
LightRAG Instance (dados isolados)
```

### 2. Autenticação (JWT)

#### Endpoints Implementados:

**POST /auth/register**
- Registra novo usuário
- Envia token de verificação de email
- Senha: mín. 8 caracteres, maiúscula, minúscula, número

**POST /auth/login**
- Autentica usuário
- Retorna access_token (1h) e refresh_token (30d)

**POST /auth/verify-email**
- Verifica email com token

**POST /auth/password-reset/request**
- Solicita reset de senha
- Envia token por email

**POST /auth/password-reset/confirm**
- Confirma reset com token

**POST /auth/refresh**
- Renova access_token com refresh_token

**POST /auth/logout**
- Revoga refresh_token

### 3. Gerenciamento de Projetos

#### Endpoints Implementados:

**POST /projects/tenants**
- Cria novo tenant (organização)
- Usuário vira owner do tenant

**POST /projects/**
- Cria projeto dentro de um tenant
- Requer permissão de owner ou admin do tenant
- Usuário vira owner do projeto

**GET /projects/my**
- Lista todos os projetos do usuário

**GET /projects/{project_id}**
- Detalhes do projeto
- Retorna role do usuário

**GET /projects/{project_id}/members**
- Lista membros do projeto

**POST /projects/{project_id}/invite**
- Convida usuário por email
- Requer role owner ou admin
- Envia token de convite

**POST /projects/invitations/accept**
- Aceita convite com token

**PUT /projects/{project_id}/members/{user_id}/role**
- Atualiza role de membro
- Requer role owner

**DELETE /projects/{project_id}/members/{user_id}**
- Remove membro
- Requer role owner

### 4. Roles de Projeto

- **OWNER**: Controle total, pode deletar projeto
- **ADMIN**: Gerenciar membros, convidar usuários
- **MEMBER**: Usar projeto, inserir/consultar documentos
- **VIEWER**: Apenas visualizar/consultar

### 5. Fluxo de Autenticação

```
1. Usuário registra → POST /auth/register
2. Verifica email → POST /auth/verify-email
3. Faz login → POST /auth/login → recebe tokens
4. Inclui header em requests:
   Authorization: Bearer {access_token}
5. Token expira → POST /auth/refresh
6. Logout → POST /auth/logout
```

### 6. Fluxo Multi-Tenant

```
1. Usuário cria tenant → POST /projects/tenants
   {
     "id": "empresa1",
     "name": "Minha Empresa",
     "description": "..."
   }

2. Cria projeto → POST /projects/
   {
     "id": "projeto_a",
     "tenant_id": "empresa1",
     "name": "Projeto A"
   }

3. Convida membros → POST /projects/{project_id}/invite
   {
     "email": "usuario@example.com",
     "role": "member"
   }

4. Membro aceita → POST /projects/invitations/accept
   {
     "token": "..."
   }

5. Usa LightRAG com headers:
   Authorization: Bearer {access_token}
   X-Tenant-ID: empresa1
   X-Project-ID: projeto_a
```

### 7. Integração com Instance Manager

O sistema de autenticação integra perfeitamente com o `LightRAGInstanceManager`:

- Middleware valida JWT e adiciona `user_id` ao request
- Extrai `X-Tenant-ID` e `X-Project-ID` dos headers
- Valida se usuário tem acesso ao projeto
- `get_rag_instance()` retorna instância correta
- Dados completamente isolados por (tenant_id, project_id)

## Implementação no Server

### Modificações Necessárias em `lightrag_server.py`:

1. **Adicionar dependências**:
```python
import asyncpg
import os
from lightrag.api.services.auth_service import AuthService
from lightrag.api.services.project_service import ProjectService
from lightrag.api.middleware.auth_middleware import AuthMiddleware
from lightrag.api.routers.auth_routes import router as auth_router
from lightrag.api.routers.project_routes import router as project_router
```

2. **Inicializar conexão PostgreSQL**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conectar ao PostgreSQL
    db_pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "lightrag"),
        password=os.getenv("POSTGRES_PASSWORD", "lightrag_password"),
        database=os.getenv("POSTGRES_DATABASE", "lightrag"),
        min_size=5,
        max_size=20
    )
    
    # Inicializar services
    auth_service = AuthService(
        db_connection=db_pool,
        secret_key=os.getenv("JWT_SECRET_KEY", "your-secret-key"),
        access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE", "60")),
        refresh_token_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    )
    
    project_service = ProjectService(db_connection=db_pool)
    
    # Armazenar no app state
    app.state.db_pool = db_pool
    app.state.auth_service = auth_service
    app.state.project_service = project_service
    app.state.instance_manager = instance_manager
    
    yield
    
    # Cleanup
    await instance_manager.shutdown()
    await db_pool.close()
```

3. **Adicionar middleware de autenticação**:
```python
app.add_middleware(AuthMiddleware, auth_service=auth_service)
```

4. **Incluir routers**:
```python
app.include_router(auth_router)
app.include_router(project_router)
```

5. **Atualizar `get_rag_instance` para validar acesso**:
```python
async def get_rag_instance(request: Request) -> LightRAG:
    tenant_id = get_tenant_id_from_request(request)
    project_id = get_project_id_from_request(request)
    
    # Validar que usuário tem acesso ao projeto
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        project_service = request.app.state.project_service
        user_role = await project_service.check_user_access(
            user_id=user_id,
            tenant_id=tenant_id,
            project_id=project_id
        )
        if not user_role:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this project"
            )
    
    return await instance_manager.get_instance(tenant_id, project_id)
```

## Variáveis de Ambiente Necessárias

Adicionar ao `.env`:

```bash
# PostgreSQL (já existe)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=lightrag_password
POSTGRES_DATABASE=lightrag

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ACCESS_TOKEN_EXPIRE=60  # minutes
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Email Configuration (para enviar convites e verificações)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=LightRAG <noreply@example.com>

# Frontend URL (para links em emails)
FRONTEND_URL=http://localhost:5173
```

## Próximos Passos

### Backend:
1. ✅ Schema de banco criado
2. ✅ Models Pydantic criados
3. ✅ Services implementados
4. ✅ Routes implementadas
5. ✅ Middleware de autenticação
6. ⏳ Integrar no lightrag_server.py
7. ⏳ Implementar envio de emails
8. ⏳ Completar migração dos routers existentes

### Frontend:
1. ⏳ Tela de Login
2. ⏳ Tela de Registro
3. ⏳ Tela de Verificação de Email
4. ⏳ Tela de Reset de Senha
5. ⏳ Seletor de Projeto/Tenant
6. ⏳ Gerenciamento de Membros
7. ⏳ Sistema de Convites
8. ⏳ Context API para auth/project
9. ⏳ Proteção de rotas
10. ⏳ Headers automáticos nas requests

## Exemplo de Uso Completo

```bash
# 1. Registrar usuário
curl -X POST http://localhost:9621/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@example.com",
    "password": "Senha123!",
    "name": "João Silva",
    "phone": "+5511999999999"
  }'

# 2. Verificar email (token recebido por email)
curl -X POST http://localhost:9621/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token": "..."}'

# 3. Login
curl -X POST http://localhost:9621/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@example.com",
    "password": "Senha123!"
  }'
# Resposta: {"access_token": "...", "refresh_token": "...", "user": {...}}

# 4. Criar tenant
curl -X POST http://localhost:9621/projects/tenants \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "empresa1",
    "name": "Minha Empresa",
    "description": "Descrição da empresa"
  }'

# 5. Criar projeto
curl -X POST http://localhost:9621/projects/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "projeto_a",
    "tenant_id": "empresa1",
    "name": "Projeto A",
    "description": "Descrição do projeto"
  }'

# 6. Inserir documento (usando projeto)
curl -X POST http://localhost:9621/documents/upload \
  -H "Authorization: Bearer {access_token}" \
  -H "X-Tenant-ID: empresa1" \
  -H "X-Project-ID: projeto_a" \
  -F "file=@documento.pdf"

# 7. Consultar (dados isolados)
curl -X POST http://localhost:9621/query/data \
  -H "Authorization: Bearer {access_token}" \
  -H "X-Tenant-ID: empresa1" \
  -H "X-Project-ID: projeto_a" \
  -H "Content-Type: application/json" \
  -d '{"query": "O que é RAG?", "mode": "hybrid"}'

# 8. Convidar membro
curl -X POST http://localhost:9621/projects/projeto_a/invite \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "colaborador@example.com",
    "role": "member"
  }'
```

## Segurança

- ✅ Senhas com bcrypt (salt automático)
- ✅ JWT com expiração
- ✅ Refresh tokens revogáveis
- ✅ Validação de permissões por projeto
- ✅ Isolamento de dados no banco
- ✅ Tokens de convite com expiração
- ✅ Email verification
- ✅ Password reset seguro
- ✅ Audit log de ações importantes

## Performance

- ✅ Connection pool PostgreSQL (5-20 conexões)
- ✅ LRU cache de instâncias LightRAG
- ✅ Índices no banco para queries rápidas
- ✅ Lazy loading de instâncias
- ✅ TTL automático para cleanup

## Testes

Para testar o sistema completo:

```bash
# 1. Subir banco
docker-compose up -d postgres

# 2. Verificar tabelas criadas
docker exec -it lightrag-postgres psql -U lightrag -d lightrag -c "\dt"

# 3. Iniciar servidor (após integração)
lightrag-server

# 4. Testar endpoints
# Use os exemplos acima
```
