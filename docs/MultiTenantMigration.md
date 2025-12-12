# Multi-Tenant Migration Guide

Este guia descreve como migrar o LightRAG para suportar múltiplos tenants (empresas) e projetos usando apenas PostgreSQL com Apache AGE (extensão de grafos).

## Visão Geral

A migração remove a dependência do Neo4j e implementa uma arquitetura multi-tenant completa onde:

- **tenant_id**: Identifica a empresa/organização
- **project_id**: Identifica o projeto dentro da empresa
- **workspace**: Identifica o ambiente (dev, staging, prod)

## Mudanças no Schema

### 1. Migração Automática (Recomendado)

O LightRAG cria e atualiza as tabelas automaticamente na inicialização. Basta atualizar o código e reiniciar:

```bash
# Atualizar código
git pull
pip install -e .

# Reiniciar - as tabelas serão atualizadas automaticamente
lightrag-server
```

### 2. Migração Manual (Apenas para bancos existentes com dados)

Se você já tem dados em produção e quer adicionar as colunas manualmente antes de atualizar o código:

```sql
-- Adicionar colunas tenant_id e project_id a todas as tabelas
ALTER TABLE LIGHTRAG_DOC_FULL 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_DOC_CHUNKS 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_VDB_CHUNKS 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_VDB_ENTITY 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_VDB_RELATION 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_LLM_CACHE 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_DOC_STATUS 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_FULL_ENTITIES 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_FULL_RELATIONS 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_ENTITY_CHUNKS 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

ALTER TABLE LIGHTRAG_RELATION_CHUNKS 
  ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255) DEFAULT 'default',
  ADD COLUMN IF NOT EXISTS project_id VARCHAR(255) DEFAULT 'default';

-- Dropar constraints existentes
ALTER TABLE LIGHTRAG_DOC_FULL DROP CONSTRAINT IF EXISTS LIGHTRAG_DOC_FULL_PK;
ALTER TABLE LIGHTRAG_DOC_CHUNKS DROP CONSTRAINT IF EXISTS LIGHTRAG_DOC_CHUNKS_PK;
ALTER TABLE LIGHTRAG_VDB_CHUNKS DROP CONSTRAINT IF EXISTS LIGHTRAG_VDB_CHUNKS_PK;
ALTER TABLE LIGHTRAG_VDB_ENTITY DROP CONSTRAINT IF EXISTS LIGHTRAG_VDB_ENTITY_PK;
ALTER TABLE LIGHTRAG_VDB_RELATION DROP CONSTRAINT IF EXISTS LIGHTRAG_VDB_RELATION_PK;
ALTER TABLE LIGHTRAG_LLM_CACHE DROP CONSTRAINT IF EXISTS LIGHTRAG_LLM_CACHE_PK;
ALTER TABLE LIGHTRAG_DOC_STATUS DROP CONSTRAINT IF EXISTS LIGHTRAG_DOC_STATUS_PK;
ALTER TABLE LIGHTRAG_FULL_ENTITIES DROP CONSTRAINT IF EXISTS LIGHTRAG_FULL_ENTITIES_PK;
ALTER TABLE LIGHTRAG_FULL_RELATIONS DROP CONSTRAINT IF EXISTS LIGHTRAG_FULL_RELATIONS_PK;
ALTER TABLE LIGHTRAG_ENTITY_CHUNKS DROP CONSTRAINT IF EXISTS LIGHTRAG_ENTITY_CHUNKS_PK;
ALTER TABLE LIGHTRAG_RELATION_CHUNKS DROP CONSTRAINT IF EXISTS LIGHTRAG_RELATION_CHUNKS_PK;

-- Adicionar novos constraints com tenant_id e project_id
ALTER TABLE LIGHTRAG_DOC_FULL 
  ADD CONSTRAINT LIGHTRAG_DOC_FULL_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_DOC_CHUNKS 
  ADD CONSTRAINT LIGHTRAG_DOC_CHUNKS_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_VDB_CHUNKS 
  ADD CONSTRAINT LIGHTRAG_VDB_CHUNKS_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_VDB_ENTITY 
  ADD CONSTRAINT LIGHTRAG_VDB_ENTITY_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_VDB_RELATION 
  ADD CONSTRAINT LIGHTRAG_VDB_RELATION_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_LLM_CACHE 
  ADD CONSTRAINT LIGHTRAG_LLM_CACHE_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_DOC_STATUS 
  ADD CONSTRAINT LIGHTRAG_DOC_STATUS_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_FULL_ENTITIES 
  ADD CONSTRAINT LIGHTRAG_FULL_ENTITIES_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_FULL_RELATIONS 
  ADD CONSTRAINT LIGHTRAG_FULL_RELATIONS_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_ENTITY_CHUNKS 
  ADD CONSTRAINT LIGHTRAG_ENTITY_CHUNKS_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

ALTER TABLE LIGHTRAG_RELATION_CHUNKS 
  ADD CONSTRAINT LIGHTRAG_RELATION_CHUNKS_PK PRIMARY KEY (tenant_id, project_id, workspace, id);

-- Criar índices para melhorar performance de queries multi-tenant
CREATE INDEX IF NOT EXISTS idx_doc_full_tenant_project ON LIGHTRAG_DOC_FULL(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_tenant_project ON LIGHTRAG_DOC_CHUNKS(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_vdb_chunks_tenant_project ON LIGHTRAG_VDB_CHUNKS(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_vdb_entity_tenant_project ON LIGHTRAG_VDB_ENTITY(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_vdb_relation_tenant_project ON LIGHTRAG_VDB_RELATION(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_llm_cache_tenant_project ON LIGHTRAG_LLM_CACHE(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_doc_status_tenant_project ON LIGHTRAG_DOC_STATUS(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_full_entities_tenant_project ON LIGHTRAG_FULL_ENTITIES(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_full_relations_tenant_project ON LIGHTRAG_FULL_RELATIONS(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_entity_chunks_tenant_project ON LIGHTRAG_ENTITY_CHUNKS(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_relation_chunks_tenant_project ON LIGHTRAG_RELATION_CHUNKS(tenant_id, project_id);
```

### 2. AGE Graphs Multi-Tenant

Os grafos AGE serão nomeados usando o padrão: `{tenant_id}_{project_id}_{workspace}_{namespace}`

Isso garante isolamento completo entre diferentes tenants e projetos.

## Uso da API

### Headers HTTP

As requisições devem incluir os seguintes headers:

```http
X-Tenant-ID: empresa1
X-Project-ID: projeto-alpha
X-Workspace: production
```

### Exemplo de Request

```bash
curl -X POST http://localhost:8020/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: empresa1" \
  -H "X-Project-ID: projeto-alpha" \
  -H "X-Workspace: production" \
  -d '{
    "query": "Qual é o status do projeto?",
    "mode": "hybrid"
  }'
```

## Variáveis de Ambiente

Remova as variáveis relacionadas ao Neo4j e mantenha apenas PostgreSQL:

```bash
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=lightrag

# Multi-tenant defaults (opcional)
DEFAULT_TENANT_ID=default
DEFAULT_PROJECT_ID=default
DEFAULT_WORKSPACE=default
```

## Benefícios da Arquitetura

1. **Isolamento Total**: Cada tenant/projeto tem dados completamente isolados
2. **Sem Neo4j**: Reduz custos e complexidade de infraestrutura
3. **Performance**: Índices otimizados para queries multi-tenant
4. **Escalabilidade**: PostgreSQL pode escalar horizontalmente
5. **AGE Graphs**: Recursos de grafos nativos do PostgreSQL

## Migração de Dados Existentes

Para migrar dados existentes sem tenant_id/project_id:

```sql
-- Atualizar registros existentes com valores default
UPDATE LIGHTRAG_DOC_FULL SET tenant_id = 'legacy', project_id = 'migration' WHERE tenant_id = 'default';
-- Repita para todas as tabelas
```

## Rollback

Se necessário fazer rollback:

```sql
-- Remover colunas adicionadas
ALTER TABLE LIGHTRAG_DOC_FULL DROP COLUMN tenant_id, DROP COLUMN project_id;
-- Repita para todas as tabelas

-- Restaurar constraints originais
ALTER TABLE LIGHTRAG_DOC_FULL DROP CONSTRAINT LIGHTRAG_DOC_FULL_PK;
ALTER TABLE LIGHTRAG_DOC_FULL ADD CONSTRAINT LIGHTRAG_DOC_FULL_PK PRIMARY KEY (workspace, id);
-- Repita para todas as tabelas
```
