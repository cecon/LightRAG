# Quick Start - Multi-Tenant LightRAG

Guia rápido para começar a usar o LightRAG com suporte multi-tenant usando PostgreSQL + Apache AGE.

## Pré-requisitos

- PostgreSQL 13+ instalado
- Python 3.9+
- Acesso a uma LLM (OpenAI, Ollama, etc.)

## Instalação

### 1. Instalar Apache AGE no PostgreSQL

```bash
# Para Ubuntu/Debian
sudo apt-get install postgresql-server-dev-all
git clone https://github.com/apache/age.git
cd age
make
sudo make install

# Conectar ao PostgreSQL
psql -U postgres

# Criar extensão AGE
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
```

### 2. Instalar LightRAG

```bash
git clone https://github.com/cecon/LightRAG.git
cd LightRAG
pip install -e .
```

### 3. Criar Banco de Dados

```bash
# Criar banco de dados
createdb -U postgres lightrag

# As tabelas serão criadas automaticamente na primeira execução
# Não é necessário executar scripts SQL manualmente
```

## Configuração

### Arquivo `.env`

Crie um arquivo `.env` na raiz do projeto:

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=lightrag
POSTGRES_MAX_CONNECTIONS=12

# Storages (use PostgreSQL para tudo)
LIGHTRAG_KV_STORAGE=PGKVStorage
LIGHTRAG_DOC_STATUS_STORAGE=PGDocStatusStorage
LIGHTRAG_GRAPH_STORAGE=PGGraphStorage
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage

# Multi-Tenant Defaults
DEFAULT_TENANT_ID=default
DEFAULT_PROJECT_ID=default

# LLM Configuration
LLM_BINDING=openai
LLM_MODEL=gpt-4o
LLM_BINDING_API_KEY=your_openai_api_key
EMBEDDING_FUNC=openai
EMBEDDING_DIM=1024
```

## Uso Básico

### Python

```python
import asyncio
from lightrag import LightRAG, QueryParam
from lightrag.llm import openai_complete_if_cache, openai_embedding

async def main():
    # Criar instância com contexto multi-tenant
    rag = LightRAG(
        working_dir="./rag_storage",
        llm_model_func=openai_complete_if_cache,
        embedding_func=openai_embedding,
        tenant_id="my_company",
        project_id="my_project",
        workspace="production"
    )
    
    # Inserir documento
    await rag.ainsert("Your document text here...")
    
    # Fazer query
    result = await rag.aquery(
        "Your question here?",
        param=QueryParam(mode="hybrid")
    )
    
    print(result)

asyncio.run(main())
```

### API Server

```bash
# Iniciar servidor
lightrag-server --workspace production --port 8020

# Fazer requisição
curl -X POST http://localhost:8020/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: my_company" \
  -H "X-Project-ID: my_project" \
  -d '{
    "query": "What is this about?",
    "mode": "hybrid"
  }'
```

## Exemplos de Uso

### Exemplo 1: Múltiplos Tenants

```python
# Empresa A
rag_company_a = LightRAG(
    tenant_id="company_a",
    project_id="sales",
    workspace="production"
)

# Empresa B
rag_company_b = LightRAG(
    tenant_id="company_b",
    project_id="sales",
    workspace="production"
)

# Dados completamente isolados!
```

### Exemplo 2: Múltiplos Projetos

```python
# Projeto 1: Customer Support
rag_support = LightRAG(
    tenant_id="my_company",
    project_id="support",
    workspace="production"
)

# Projeto 2: Product Docs
rag_docs = LightRAG(
    tenant_id="my_company",
    project_id="docs",
    workspace="production"
)
```

### Exemplo 3: Múltiplos Ambientes

```python
# Desenvolvimento
rag_dev = LightRAG(
    tenant_id="my_company",
    project_id="main",
    workspace="development"
)

# Produção
rag_prod = LightRAG(
    tenant_id="my_company",
    project_id="main",
    workspace="production"
)
```

## Verificação

### Verificar Instalação do AGE

```sql
SELECT * FROM pg_extension WHERE extname = 'age';
```

### Verificar Schema

```sql
SELECT table_name, column_name 
FROM information_schema.columns
WHERE table_name = 'lightrag_doc_status'
  AND column_name IN ('tenant_id', 'project_id');
```

### Verificar Dados

```sql
SELECT tenant_id, project_id, workspace, COUNT(*) 
FROM lightrag_doc_status
GROUP BY tenant_id, project_id, workspace;
```

## Troubleshooting

### Erro: "extension age does not exist"

**Solução:**
```sql
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
```

### Erro: "could not open extension control file"

**Solução:** Reinstale o Apache AGE
```bash
cd age
sudo make install
```

### Erro: Connection refused

**Solução:** Verifique PostgreSQL está rodando
```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### Performance lenta

**Solução:** Execute ANALYZE
```sql
ANALYZE lightrag_doc_full;
ANALYZE lightrag_vdb_entity;
-- Repita para todas as tabelas
```

## Próximos Passos

1. Leia a [Documentação Completa](./MultiTenantArchitecture.md)
2. Veja [Exemplos Avançados](../examples/multi_tenant_example.py)
3. Configure [Autenticação e Segurança](./Security.md)
4. Implemente [Monitoramento](./Monitoring.md)

## Recursos

- [Documentação PostgreSQL](https://www.postgresql.org/docs/)
- [Apache AGE Documentation](https://age.apache.org/docs/)
- [LightRAG Repository](https://github.com/cecon/LightRAG)
- [Issues e Suporte](https://github.com/cecon/LightRAG/issues)

## Comandos Úteis

```bash
# Backup
pg_dump -U postgres lightrag > backup.sql

# Restore
psql -U postgres lightrag < backup.sql

# Ver logs PostgreSQL
tail -f /var/log/postgresql/postgresql-*.log

# Iniciar servidor em background
nohup lightrag-server --workspace production > server.log 2>&1 &

# Parar servidor
pkill -f lightrag-server

# Limpar dados de um tenant específico
psql -U postgres lightrag -c "
  DELETE FROM lightrag_doc_status 
  WHERE tenant_id = 'my_company' 
    AND project_id = 'my_project';
"
```

## Dicas de Performance

1. **Índices**: Os índices multi-tenant já estão criados pela migration
2. **Pool de Conexões**: Ajuste `POSTGRES_MAX_CONNECTIONS` baseado na carga
3. **Vacuum**: Execute periodicamente
   ```sql
   VACUUM ANALYZE;
   ```
4. **Particionamento**: Para muitos tenants, considere particionamento por tenant_id

## Segurança

1. **Row-Level Security**: Implemente RLS para isolamento adicional
2. **Conexões SSL**: Configure SSL no PostgreSQL
3. **Secrets**: Use variáveis de ambiente, não hardcode
4. **Auditing**: Implemente logging de acesso por tenant

## FAQ Rápido

**P: Quantos tenants posso ter?**  
R: Teoricamente ilimitado, limitado apenas pela capacidade do PostgreSQL.

**P: Os dados são realmente isolados?**  
R: Sim, através das primary keys compostas e naming de grafos AGE.

**P: Posso migrar de Neo4j?**  
R: Sim, mas Neo4j foi removido. Use apenas PostgreSQL+AGE.

**P: Como faço backup de um tenant específico?**  
R: Use queries SQL com WHERE tenant_id = 'xxx'.

**P: Posso usar Redis para cache?**  
R: Sim, configure `LIGHTRAG_KV_STORAGE=RedisKVStorage` para cache.
