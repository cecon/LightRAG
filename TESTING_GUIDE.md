# Guia Rápido: Testar Sistema Multi-Tenant

## Pré-requisitos

1. Docker e Docker Compose instalados
2. Arquivos `.env` configurado
3. Portas 5432 (PostgreSQL) e 9621 (LightRAG) disponíveis

## Passo 1: Configurar Environment

```bash
# Copiar exemplo
cp env.example .env

# Editar .env (IMPORTANTE!)
nano .env
```

**Configurações mínimas necessárias**:
```bash
# Multi-Tenant
LIGHTRAG_MULTI_TENANT=true

# PostgreSQL
POSTGRES_HOST=postgres  # Nome do serviço no docker-compose
POSTGRES_PORT=5432
POSTGRES_DB=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=SuaSenhaSegura123!

# JWT
JWT_SECRET_KEY=$(openssl rand -base64 32)  # Gerar key segura
JWT_ALGORITHM=HS256

# LLM Encryption
LLM_CONFIG_ENCRYPTION_KEY=$(openssl rand -base64 32)  # Gerar key segura
```

## Passo 2: Subir o Docker

```bash
# Limpar volumes antigos (CUIDADO: apaga dados!)
docker-compose down -v

# Subir serviços
docker-compose up -d

# Verificar logs
docker-compose logs -f

# Aguardar PostgreSQL inicializar (até ver "database system is ready to accept connections")
```

## Passo 3: Verificar Saúde do Sistema

```bash
# Health check
curl http://localhost:9621/health

# Verificar banco de dados
docker-compose exec postgres psql -U lightrag -d lightrag -c "\dt"

# Deve mostrar tabelas:
# - lightrag_users
# - lightrag_tenants
# - lightrag_projects
# - lightrag_api_keys
# - lightrag_llm_configs
# + outras tabelas LightRAG
```

## Passo 4: Executar Teste Automatizado

```bash
# Dar permissão de execução
chmod +x test-multi-tenant.sh

# Executar teste
./test-multi-tenant.sh
```

**O script irá**:
1. ✅ Verificar se servidor está rodando
2. ✅ Registrar usuário de teste
3. ✅ Fazer login (obter JWT)
4. ✅ Criar tenant
5. ✅ Criar projeto
6. ✅ Configurar LLM (Ollama)
7. ✅ Criar API key

## Passo 5: Teste Manual (Opcional)

### 5.1 Registrar Usuário

```bash
curl -X POST http://localhost:9621/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "Admin123!",
    "full_name": "Admin User"
  }'
```

### 5.2 Login

```bash
curl -X POST http://localhost:9621/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "Admin123!"
  }'

# Salvar o access_token
JWT="eyJhbGc..."
```

### 5.3 Criar Tenant

```bash
curl -X POST http://localhost:9621/projects/tenants \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company",
    "description": "Test company"
  }'

# Salvar tenant_id
TENANT_ID="uuid-aqui"
```

### 5.4 Criar Projeto

```bash
curl -X POST http://localhost:9621/projects \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "'$TENANT_ID'",
    "name": "Documentation",
    "description": "Docs RAG"
  }'

# Salvar project_id
PROJECT_ID="uuid-aqui"
```

### 5.5 Configurar LLM

**Opção A: OpenAI**
```bash
curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'$PROJECT_ID'",
    "name": "Production OpenAI",
    "provider": "openai",
    "api_key": "sk-...",
    "model_name": "gpt-4-turbo-preview",
    "is_default": true
  }'
```

**Opção B: Ollama (Local)**
```bash
# Primeiro, certifique-se que Ollama está rodando:
# docker run -d -p 11434:11434 --name ollama ollama/ollama
# docker exec -it ollama ollama pull llama2

curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'$PROJECT_ID'",
    "name": "Local Llama",
    "provider": "ollama",
    "model_name": "llama2",
    "base_url": "http://host.docker.internal:11434",
    "is_default": true
  }'
```

### 5.6 Criar API Key

```bash
curl -X POST http://localhost:9621/api-keys \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'$PROJECT_ID'",
    "name": "Production API",
    "scopes": ["query", "insert", "delete"]
  }'

# ⚠️ COPIE A KEY AGORA! Não será mostrada novamente
API_KEY="lrag_..."
```

### 5.7 Testar Inserção de Documento

```bash
curl -X POST http://localhost:9621/documents \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "LightRAG is a retrieval-augmented generation framework that uses graph-based knowledge representation."
  }'
```

### 5.8 Testar Query

```bash
curl -X POST http://localhost:9621/query/data \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is LightRAG?",
    "mode": "hybrid"
  }'
```

## Troubleshooting

### Erro: "Server not responding"

```bash
# Verificar status dos containers
docker-compose ps

# Ver logs do LightRAG
docker-compose logs lightrag

# Ver logs do PostgreSQL
docker-compose logs postgres
```

### Erro: "No LLM configuration found"

```bash
# Verificar se configuração existe no banco
docker-compose exec postgres psql -U lightrag -d lightrag -c \
  "SELECT id, name, provider, model_name, is_default FROM lightrag_llm_configs;"

# Se vazio, criar configuração via API (passo 5.5)
```

### Erro: "Authentication required"

```bash
# Verificar se JWT está válido
curl http://localhost:9621/auth/me \
  -H "Authorization: Bearer $JWT"

# Se expirou, fazer novo login (passo 5.2)
```

### Erro: "Database connection failed"

```bash
# Verificar se PostgreSQL está rodando
docker-compose ps postgres

# Testar conexão
docker-compose exec postgres psql -U lightrag -d lightrag -c "SELECT 1;"

# Verificar se tabelas foram criadas
docker-compose exec postgres psql -U lightrag -d lightrag -c "\dt"
```

### Resetar Banco de Dados

```bash
# ⚠️ CUIDADO: Apaga TODOS os dados!
docker-compose down -v
docker-compose up -d
```

## Validação Completa

Checklist de funcionalidades:

- [ ] ✅ PostgreSQL rodando com AGE extension
- [ ] ✅ Servidor LightRAG respondendo em `/health`
- [ ] ✅ Registro de usuário funcionando
- [ ] ✅ Login retornando JWT token
- [ ] ✅ Criação de tenant
- [ ] ✅ Criação de projeto
- [ ] ✅ Configuração de LLM salva no banco (criptografada)
- [ ] ✅ Criação de API key
- [ ] ✅ Inserção de documento com API key
- [ ] ✅ Query funcionando com LLM do banco

## Logs Úteis

```bash
# Logs em tempo real
docker-compose logs -f

# Apenas LightRAG
docker-compose logs -f lightrag

# Apenas PostgreSQL
docker-compose logs -f postgres

# Últimas 100 linhas
docker-compose logs --tail=100 lightrag
```

## Próximos Passos

1. Implementar frontend UI
2. Configurar email service (SMTP)
3. Testar múltiplos providers (OpenAI, Azure, Anthropic)
4. Performance testing com múltiplos projetos
5. Implementar migração de configs do .env para banco
