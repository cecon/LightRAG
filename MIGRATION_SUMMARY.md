# Sumário das Alterações - Multi-Tenant Migration

## Objetivo
Migrar o LightRAG para abandonar o Neo4j e usar exclusivamente PostgreSQL com Apache AGE, implementando arquitetura multi-tenant com suporte a múltiplas empresas e projetos.

## Alterações Realizadas

### 1. Schema do Banco de Dados ✅

#### Tabelas Atualizadas
Todas as tabelas PostgreSQL foram modificadas para incluir:
- `tenant_id VARCHAR(255) DEFAULT 'default'` - Identificador da empresa/organização
- `project_id VARCHAR(255) DEFAULT 'default'` - Identificador do projeto

**Tabelas afetadas:**
- LIGHTRAG_DOC_FULL
- LIGHTRAG_DOC_CHUNKS
- LIGHTRAG_VDB_CHUNKS
- LIGHTRAG_VDB_ENTITY
- LIGHTRAG_VDB_RELATION
- LIGHTRAG_LLM_CACHE
- LIGHTRAG_DOC_STATUS
- LIGHTRAG_FULL_ENTITIES
- LIGHTRAG_FULL_RELATIONS
- LIGHTRAG_ENTITY_CHUNKS
- LIGHTRAG_RELATION_CHUNKS

#### Primary Keys
Atualizados de `(workspace, id)` para `(tenant_id, project_id, workspace, id)`

#### Índices
Criados índices compostos para otimizar queries multi-tenant:
```sql
CREATE INDEX idx_{table}_tenant_project ON {table}(tenant_id, project_id);
CREATE INDEX idx_{table}_tenant_project_workspace ON {table}(tenant_id, project_id, workspace);
```

### 2. Código Base ✅

#### `lightrag/base.py`
```python
@dataclass
class StorageNameSpace(ABC):
    namespace: str
    workspace: str
    global_config: dict[str, Any]
    tenant_id: str = field(default="default")  # NOVO
    project_id: str = field(default="default")  # NOVO
```

#### `lightrag/kg/postgres_impl.py`

**PGGraphStorage:**
- Método `_get_workspace_graph_name()` atualizado para incluir tenant_id e project_id
- Grafos AGE nomeados como: `{tenant_id}_{project_id}_{workspace}_{namespace}`
- Logging melhorado com informações de tenant/project

**Exemplo de log:**
```
[tenant=company_a][project=sales][workspace=prod] PostgreSQL Graph initialized: graph_name='company_a_sales_prod_entities'
```

### 3. Remoção do Neo4j ✅

#### Arquivos Modificados

**`lightrag/kg/__init__.py`:**
- Removido `Neo4JStorage` de `GRAPH_STORAGE implementations`
- Removido mapeamento `"Neo4JStorage": ".kg.neo4j_impl"`
- Removidas variáveis de ambiente Neo4j de `STORAGE_ENV_REQUIREMENTS`

**`requirements-offline-storage.txt`:**
- Removida dependência `neo4j>=5.0.0,<7.0.0`
- Adicionado comentário explicando uso de PostgreSQL+AGE

**`config.ini.example`:**
- Removida seção `[neo4j]`
- Reorganizada seção `[postgres]` com comentários sobre multi-tenant

**`env.example`:**
- Removidas todas as variáveis `NEO4J_*`
- Adicionadas variáveis `DEFAULT_TENANT_ID` e `DEFAULT_PROJECT_ID`
- Atualizado `LIGHTRAG_GRAPH_STORAGE` para recomendar `PGGraphStorage`

### 5. Migração Automática ✅

O LightRAG cria e atualiza tabelas automaticamente via Python:
- Método `check_tables()` em `postgres_impl.py` cria tabelas se não existirem
- Definições em `TABLES` dict incluem tenant_id e project_id
- Não há necessidade de scripts SQL manuais
- Para bancos existentes: script SQL de referência disponível em `docs/`

### 5. Documentação ✅

#### `docs/MultiTenantMigration.md`
Guia completo de migração incluindo:
- Visão geral da arquitetura
- Scripts SQL de migração
- Comandos de rollback
- Exemplos de uso da API
- Configuração de variáveis de ambiente

#### `docs/MultiTenantArchitecture.md`
Documentação completa da arquitetura:
- Benefícios do PostgreSQL + AGE
- Modelo de isolamento de dados
- Exemplos de uso (cURL, Python)
- Guias de configuração
- Considerações de performance
- Segurança e monitoramento
- Troubleshooting
- Best practices
- FAQ

## Próximos Passos (Pendentes)

### 5. Atualizar Storages PostgreSQL ⏳
**Tarefas:**
- Modificar PGKVStorage para incluir tenant_id e project_id em todas queries SQL
- Atualizar PGVectorStorage com filtros multi-tenant
- Modificar PGDocStatusStorage para suportar tenant/project
- Atualizar SQL_TEMPLATES com novos parâmetros

**Arquivos a modificar:**
- `lightrag/kg/postgres_impl.py` (classes de storage)

### 6. Modificar LightRAG Core ⏳
**Tarefas:**
- Atualizar classe `LightRAG` em `lightrag/lightrag.py` para aceitar tenant_id e project_id
- Propagar esses valores para todos os storages durante inicialização
- Adicionar métodos para alternar contexto de tenant/project

**Exemplo esperado:**
```python
rag = LightRAG(
    working_dir="./rag_storage",
    tenant_id="company_a",
    project_id="project_alpha",
    workspace="production"
)
```

### 7. Atualizar API Endpoints ⏳
**Tarefas:**
- Modificar `lightrag/api/lightrag_server.py` para extrair headers `X-Tenant-ID`, `X-Project-ID`
- Atualizar routers para passar tenant/project para LightRAG
- Adicionar validação de tenant/project
- Implementar middleware para logging de contexto multi-tenant

**Headers esperados:**
```http
X-Tenant-ID: company_a
X-Project-ID: project_alpha
X-Workspace: production
```

## Como Executar a Migração

### Passo 1: Backup
```bash
pg_dump -U lightrag lightrag > lightrag_backup_$(date +%Y%m%d).sql
```

### Passo 2: Instalar Apache AGE
```sql
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
```

### Passo 3: Inicializar Sistema
```bash
# As tabelas serão criadas/atualizadas automaticamente
# Basta iniciar o LightRAG
python your_app.py
# ou
lightrag-server
```

### Passo 4: Atualizar Código
```bash
git pull  # Obter as alterações
pip install -e .  # Reinstalar pacote
```

### Passo 5: Atualizar Configuração
```bash
# .env
LIGHTRAG_GRAPH_STORAGE=PGGraphStorage
# Remover variáveis NEO4J_*
DEFAULT_TENANT_ID=default
DEFAULT_PROJECT_ID=default
```

### Passo 6: Reiniciar Aplicação
```bash
lightrag-server --workspace production
```

## Verificação

### Verificar Schema
```sql
SELECT table_name, column_name 
FROM information_schema.columns
WHERE table_name LIKE 'lightrag_%'
  AND column_name IN ('tenant_id', 'project_id')
ORDER BY table_name;
```

### Verificar Índices
```sql
SELECT indexname, tablename
FROM pg_indexes
WHERE tablename LIKE 'lightrag_%'
  AND indexname LIKE '%tenant%'
ORDER BY tablename;
```

### Testar API
```bash
curl -X POST http://localhost:8020/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: test_tenant" \
  -H "X-Project-ID: test_project" \
  -d '{"query": "test", "mode": "naive"}'
```

## Arquivos Criados/Modificados

### Criados
- ✅ `docs/MultiTenantMigration.md` - Guia de migração
- ✅ `docs/MultiTenantArchitecture.md` - Documentação da arquitetura
- ✅ `docs/QuickStart-MultiTenant.md` - Guia rápido
- ✅ `examples/multi_tenant_example.py` - Exemplos práticos
- ✅ `MIGRATION_SUMMARY.md` - Este arquivo

### Modificados
- ✅ `lightrag/base.py` - Adicionados tenant_id e project_id ao StorageNameSpace
- ✅ `lightrag/kg/postgres_impl.py` - Atualizado TABLES e PGGraphStorage
- ✅ `lightrag/kg/__init__.py` - Removido Neo4JStorage
- ✅ `requirements-offline-storage.txt` - Removido neo4j
- ✅ `config.ini.example` - Removida seção neo4j
- ✅ `env.example` - Removidas variáveis NEO4J_*

### A Modificar (Próximos Passos)
- ⏳ `lightrag/lightrag.py` - Adicionar suporte a tenant_id/project_id
- ⏳ `lightrag/api/lightrag_server.py` - Extrair headers multi-tenant
- ⏳ `lightrag/api/routers/*.py` - Atualizar endpoints
- ⏳ `lightrag/kg/postgres_impl.py` - Completar storages restantes

## Benefícios da Nova Arquitetura

1. **Simplicidade**: Um único banco de dados (PostgreSQL) para tudo
2. **Custo**: Elimina necessidade de infraestrutura Neo4j separada
3. **Isolamento**: Dados completamente isolados por tenant/project/workspace
4. **Performance**: Índices otimizados para queries multi-tenant
5. **Escalabilidade**: PostgreSQL pode escalar horizontalmente
6. **Manutenção**: Backup e restore simplificados
7. **Grafos Nativos**: Apache AGE fornece Cypher queries como Neo4j

## Compatibilidade

### Backward Compatibility
- Valores default `'default'` para tenant_id e project_id
- Queries existentes continuam funcionando com tenant/project default
- Migração gradual possível

### Breaking Changes
- Neo4j não é mais suportado
- Primary keys mudaram (pode afetar queries diretas ao banco)
- Grafos AGE têm naming convention diferente

## Rollback (Se Necessário)

```sql
-- Remover colunas
ALTER TABLE LIGHTRAG_DOC_FULL DROP COLUMN tenant_id, DROP COLUMN project_id;
-- Repetir para todas as tabelas

-- Restaurar primary keys originais
ALTER TABLE LIGHTRAG_DOC_FULL DROP CONSTRAINT LIGHTRAG_DOC_FULL_PK;
ALTER TABLE LIGHTRAG_DOC_FULL ADD CONSTRAINT LIGHTRAG_DOC_FULL_PK 
  PRIMARY KEY (workspace, id);
-- Repetir para todas as tabelas
```

## Suporte

- Issues: https://github.com/cecon/LightRAG/issues
- Documentação: `/docs` folder
- Exemplos: `/examples` folder
