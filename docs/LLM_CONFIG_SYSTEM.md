# LLM Configuration System

## Overview

O LightRAG agora suporta **configurações de LLM por projeto**, eliminando a dependência de variáveis de ambiente `.env` para credenciais de IA.

Cada usuário/projeto pode ter suas próprias:
- ✅ API keys de diferentes provedores (OpenAI, Azure, Anthropic, etc.)
- ✅ Modelos e parâmetros personalizados
- ✅ Configurações de embedding
- ✅ Múltiplas configurações por projeto (produção, desenvolvimento, testes)

## Motivação

### Problema Anterior
- ❌ Todas as credenciais no arquivo `.env`
- ❌ Um único provedor/modelo para todos os projetos
- ❌ Impossível em ambiente multi-tenant
- ❌ Troca de credenciais requer restart do servidor

### Nova Solução
- ✅ Credenciais criptografadas no banco de dados
- ✅ Cada projeto com suas próprias configurações
- ✅ Suporte a múltiplos provedores simultaneamente
- ✅ Configurações podem ser alteradas em tempo real via API

## Arquitetura

### Database Schema

```sql
CREATE TABLE lightrag_llm_configs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES lightrag_users(id),
    tenant_id UUID REFERENCES lightrag_tenants(id),
    project_id UUID REFERENCES lightrag_projects(id),
    
    name VARCHAR(255),                    -- "Production OpenAI", "Dev Ollama"
    provider VARCHAR(50),                 -- openai, azure_openai, ollama, etc.
    
    api_key_encrypted BYTEA,              -- Criptografado com pgcrypto
    model_name VARCHAR(255),              -- gpt-4, claude-3-opus, llama2
    base_url VARCHAR(500),                -- Custom endpoint URL
    
    temperature DECIMAL(3,2),
    max_tokens INTEGER,
    top_p DECIMAL(3,2),
    
    embedding_model VARCHAR(255),         -- Modelo separado para embeddings
    embedding_base_url VARCHAR(500),
    embedding_api_key_encrypted BYTEA,
    
    additional_config JSONB,              -- Configurações específicas do provider
    
    is_active BOOLEAN,
    is_default BOOLEAN,                   -- Config padrão do projeto
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_used_at TIMESTAMP
);
```

### Providers Suportados

| Provider | Nome | Requer API Key | Exemplo de Modelo |
|----------|------|----------------|-------------------|
| `openai` | OpenAI | ✅ | gpt-4-turbo-preview, gpt-3.5-turbo |
| `azure_openai` | Azure OpenAI | ✅ | gpt-4, gpt-35-turbo |
| `ollama` | Ollama (local) | ❌ | llama2, mistral, codellama |
| `anthropic` | Anthropic Claude | ✅ | claude-3-opus, claude-3-sonnet |
| `gemini` | Google Gemini | ✅ | gemini-pro, gemini-ultra |
| `bedrock` | AWS Bedrock | ✅ | anthropic.claude-v2 |
| `huggingface` | HuggingFace | ✅ | meta-llama/Llama-2-70b |
| `openai_compatible` | Qualquer API compatível | Opcional | Depende do provider |

### Segurança - Criptografia de API Keys

```sql
-- Função de criptografia (usando pgcrypto)
CREATE FUNCTION encrypt_api_key(api_key TEXT, encryption_key TEXT)
RETURNS BYTEA AS $$
    RETURN pgp_sym_encrypt(api_key, encryption_key);
$$ LANGUAGE plpgsql;

-- Função de descriptografia
CREATE FUNCTION decrypt_api_key(encrypted_key BYTEA, encryption_key TEXT)
RETURNS TEXT AS $$
    RETURN pgp_sym_decrypt(encrypted_key, encryption_key);
$$ LANGUAGE plpgsql;
```

**Chave de Criptografia**: `LLM_CONFIG_ENCRYPTION_KEY` (mínimo 32 caracteres)

## API Endpoints

### 1. Criar Configuração de LLM

```bash
POST /llm-configs
```

**Exemplo: OpenAI**
```bash
curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-uuid",
    "name": "Production OpenAI",
    "provider": "openai",
    "api_key": "sk-...",
    "model_name": "gpt-4-turbo-preview",
    "temperature": 0.7,
    "max_tokens": 4000,
    "is_default": true
  }'
```

**Exemplo: Ollama (local, sem API key)**
```bash
curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-uuid",
    "name": "Local Llama",
    "provider": "ollama",
    "model_name": "llama2",
    "base_url": "http://localhost:11434",
    "temperature": 0.7,
    "is_default": false
  }'
```

**Exemplo: Azure OpenAI com embedding separado**
```bash
curl -X POST http://localhost:9621/llm-configs \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-uuid",
    "name": "Azure OpenAI",
    "provider": "azure_openai",
    "api_key": "your-azure-key",
    "model_name": "gpt-4",
    "base_url": "https://your-resource.openai.azure.com",
    "embedding_model": "text-embedding-ada-002",
    "embedding_api_key": "your-azure-key",
    "additional_config": {
      "api_version": "2023-05-15",
      "deployment_name": "gpt-4-deployment"
    },
    "temperature": 0.7,
    "is_default": true
  }'
```

**Response:**
```json
{
  "id": "config-uuid",
  "name": "Production OpenAI",
  "provider": "openai",
  "model_name": "gpt-4-turbo-preview",
  "temperature": 0.7,
  "max_tokens": 4000,
  "has_api_key": true,  // Boolean flag, nunca expõe a key
  "is_default": true,
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 2. Listar Configurações do Projeto

```bash
GET /llm-configs/project/{project_id}
```

```bash
curl -X GET http://localhost:9621/llm-configs/project/proj-uuid \
  -H "Authorization: Bearer <jwt-token>"
```

**Response:**
```json
[
  {
    "id": "config-1",
    "name": "Production OpenAI",
    "provider": "openai",
    "model_name": "gpt-4-turbo-preview",
    "is_default": true,
    "has_api_key": true,
    "last_used_at": "2024-01-15T14:20:00Z"
  },
  {
    "id": "config-2",
    "name": "Local Llama",
    "provider": "ollama",
    "model_name": "llama2",
    "is_default": false,
    "has_api_key": false,
    "last_used_at": null
  }
]
```

### 3. Atualizar Configuração

```bash
PUT /llm-configs/{config_id}
```

**Exemplo: Trocar API key**
```bash
curl -X PUT http://localhost:9621/llm-configs/config-uuid \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "sk-new-key...",
    "model_name": "gpt-4-turbo"
  }'
```

**Exemplo: Definir como padrão**
```bash
curl -X PUT http://localhost:9621/llm-configs/config-uuid \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "is_default": true
  }'
```

### 4. Deletar Configuração

```bash
DELETE /llm-configs/{config_id}
```

```bash
curl -X DELETE http://localhost:9621/llm-configs/config-uuid \
  -H "Authorization: Bearer <jwt-token>"
```

## Integração com LightRAG

### Como funciona

1. **Usuário cria configuração de LLM** via API
2. **Marca uma como padrão** para o projeto
3. **Instance Manager consulta configuração** ao criar instância LightRAG
4. **LightRAG é inicializado** com as credenciais do banco, não do `.env`

### Instance Manager (Atualização Pendente)

```python
# lightrag/api/instance_manager.py
async def get_instance(self, tenant_id: str, project_id: str) -> LightRAG:
    # Buscar configuração de LLM do banco
    llm_config = await llm_config_service.get_default_config(project_id)
    
    if not llm_config:
        raise ValueError(f"No LLM config found for project {project_id}")
    
    # Configurar LLM baseado no provider
    if llm_config["provider"] == "openai":
        llm_func = create_openai_llm(
            api_key=llm_config["api_key"],
            model=llm_config["model_name"],
            temperature=llm_config["temperature"]
        )
    elif llm_config["provider"] == "ollama":
        llm_func = create_ollama_llm(
            base_url=llm_config["base_url"],
            model=llm_config["model_name"]
        )
    # ... outros providers
    
    # Criar instância LightRAG
    rag = LightRAG(
        working_dir=f"./rag_storage/{tenant_id}/{project_id}",
        llm_model_func=llm_func,
        embedding_func=embedding_func,
        # ... outras configs
    )
    
    return rag
```

## Código Components

### 1. LLMConfigService
**Arquivo**: [lightrag/api/services/llm_config_service.py](../lightrag/api/services/llm_config_service.py)

**Métodos principais:**
- `create_config()`: Criar nova configuração (criptografa API key)
- `get_config_by_id()`: Buscar config (sem API key descriptografada)
- `get_decrypted_config()`: Buscar config com API key descriptografada (uso interno)
- `get_project_configs()`: Listar todas as configs de um projeto
- `get_default_config()`: Buscar config padrão de um projeto (para instance manager)
- `update_config()`: Atualizar configuração
- `delete_config()`: Deletar configuração

### 2. LLM Config Routes
**Arquivo**: [lightrag/api/routers/llm_config_routes.py](../lightrag/api/routers/llm_config_routes.py)

**Endpoints:**
- `POST /llm-configs`: Criar configuração
- `GET /llm-configs/project/{project_id}`: Listar configurações
- `GET /llm-configs/{config_id}`: Obter configuração específica
- `PUT /llm-configs/{config_id}`: Atualizar configuração
- `DELETE /llm-configs/{config_id}`: Deletar configuração

### 3. Pydantic Models
**Arquivo**: [lightrag/api/models/auth_models.py](../lightrag/api/models/auth_models.py)

```python
class LLMProvider(Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    BEDROCK = "bedrock"
    HUGGINGFACE = "huggingface"
    OPENAI_COMPATIBLE = "openai_compatible"

class LLMConfigRequest(BaseModel):
    project_id: str
    name: str
    provider: LLMProvider
    api_key: Optional[str]
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4000
    # ... outros campos

class LLMConfigResponse(BaseModel):
    id: str
    name: str
    provider: LLMProvider
    model_name: str
    has_api_key: bool  # Boolean flag, nunca expõe a chave real
    is_default: bool
    # ... outros campos
```

## Environment Variables

Adicione ao `.env`:

```bash
# LLM Configuration Encryption Key
# IMPORTANTE: Gere uma chave segura com: openssl rand -base64 32
LLM_CONFIG_ENCRYPTION_KEY=your-secure-random-key-minimum-32-characters
```

## Frontend UI (Próximos Passos)

### Tela de Configuração de LLM

```typescript
// Componente de gerenciamento de LLM configs
const LLMConfigPanel = () => {
  const [configs, setConfigs] = useState([]);
  
  // Listar configurações
  useEffect(() => {
    fetch(`/llm-configs/project/${projectId}`, {
      headers: { 'Authorization': `Bearer ${jwtToken}` }
    })
    .then(res => res.json())
    .then(setConfigs);
  }, [projectId]);
  
  // Criar nova configuração
  const createConfig = async (data) => {
    await fetch('/llm-configs', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });
  };
  
  return (
    <div>
      <h2>LLM Configurations</h2>
      
      {/* Lista de configurações */}
      {configs.map(config => (
        <ConfigCard key={config.id} config={config} />
      ))}
      
      {/* Botão para adicionar */}
      <button onClick={() => setShowForm(true)}>
        Add LLM Configuration
      </button>
      
      {/* Form de criação */}
      {showForm && <CreateConfigForm onSubmit={createConfig} />}
    </div>
  );
};
```

### Form de Criação

```typescript
const CreateConfigForm = ({ onSubmit }) => {
  const [provider, setProvider] = useState('openai');
  const [formData, setFormData] = useState({
    name: '',
    api_key: '',
    model_name: '',
    temperature: 0.7,
    max_tokens: 4000
  });
  
  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      onSubmit({ ...formData, provider });
    }}>
      <select value={provider} onChange={e => setProvider(e.target.value)}>
        <option value="openai">OpenAI</option>
        <option value="azure_openai">Azure OpenAI</option>
        <option value="ollama">Ollama (Local)</option>
        <option value="anthropic">Anthropic Claude</option>
        <option value="gemini">Google Gemini</option>
      </select>
      
      <input
        placeholder="Configuration Name"
        value={formData.name}
        onChange={e => setFormData({...formData, name: e.target.value})}
      />
      
      {provider !== 'ollama' && (
        <input
          type="password"
          placeholder="API Key"
          value={formData.api_key}
          onChange={e => setFormData({...formData, api_key: e.target.value})}
        />
      )}
      
      <input
        placeholder="Model Name"
        value={formData.model_name}
        onChange={e => setFormData({...formData, model_name: e.target.value})}
      />
      
      <button type="submit">Create Configuration</button>
    </form>
  );
};
```

## Migration Guide

### Para Usuários Existentes

1. **Criar primeira configuração de LLM**:
   ```bash
   # Login para obter token JWT
   curl -X POST http://localhost:9621/auth/login \
     -d '{"email": "admin@example.com", "password": "admin123"}'
   
   # Criar configuração
   curl -X POST http://localhost:9621/llm-configs \
     -H "Authorization: Bearer <token>" \
     -d '{
       "project_id": "default-project",
       "name": "My OpenAI Config",
       "provider": "openai",
       "api_key": "sk-...",
       "model_name": "gpt-4",
       "is_default": true
     }'
   ```

2. **Verificar configuração**:
   ```bash
   curl -X GET http://localhost:9621/llm-configs/project/default-project \
     -H "Authorization: Bearer <token>"
   ```

3. **Testar query** (agora usa config do banco):
   ```bash
   curl -X POST http://localhost:9621/query/data \
     -H "Authorization: Bearer lrag_..." \
     -d '{"query": "What is RAG?", "mode": "hybrid"}'
   ```

## Testing

```python
# tests/test_llm_config_service.py
async def test_create_openai_config():
    config = await llm_service.create_config(
        user_id=user_id,
        request=LLMConfigRequest(
            project_id=project_id,
            name="Test OpenAI",
            provider=LLMProvider.OPENAI,
            api_key="sk-test...",
            model_name="gpt-4"
        )
    )
    assert config.has_api_key == True
    assert config.is_default == False

async def test_get_default_config():
    # Buscar config padrão (com chave descriptografada)
    config = await llm_service.get_default_config(project_id)
    assert config["api_key"].startswith("sk-")
    assert config["provider"] == "openai"
```

## Security Best Practices

1. **Chave de Criptografia**:
   - Gere com `openssl rand -base64 32`
   - Armazene em secret manager (AWS Secrets, Vault, etc.)
   - Nunca commit no git

2. **API Keys no Banco**:
   - Sempre criptografadas com pgcrypto
   - Nunca retornadas em responses (apenas `has_api_key: true`)
   - Descriptografadas apenas no instance manager

3. **Permissões**:
   - Apenas membros do projeto podem criar/ver configs
   - Apenas owners/admins podem deletar configs
   - Cada request valida permissões via `project_service`

## Próximos Passos

- [x] Criar tabela `lightrag_llm_configs`
- [x] Criar `LLMConfigService` com criptografia
- [x] Criar rotas `/llm-configs`
- [x] Adicionar modelos Pydantic
- [x] Atualizar `docker-compose.yml` e `env.example`
- [ ] **Atualizar `instance_manager` para usar configs do banco**
- [ ] Criar UI de gerenciamento de LLM configs
- [ ] Testes de integração
- [ ] Documentação de providers específicos (Azure, Bedrock, etc.)
- [ ] Migração automática de configs do `.env` para banco

## References

- [Database Schema](../init-llm-configs-table.sql)
- [LLM Config Service](../lightrag/api/services/llm_config_service.py)
- [LLM Config Routes](../lightrag/api/routers/llm_config_routes.py)
- [Pydantic Models](../lightrag/api/models/auth_models.py)
- [Multi-Tenant Implementation](./MULTI_TENANT_IMPLEMENTATION.md)
- [API Keys Integration](./API_KEYS_INTEGRATION.md)
