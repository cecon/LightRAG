-- LLM Configuration Table
-- Stores LLM provider credentials and settings per user/project
-- Allows each user/project to have their own API keys and model preferences

CREATE TABLE IF NOT EXISTS lightrag_llm_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE CASCADE,
    tenant_id VARCHAR(255) NOT NULL REFERENCES lightrag_tenants(id) ON DELETE CASCADE,
    project_id VARCHAR(255) NOT NULL REFERENCES lightrag_projects(id) ON DELETE CASCADE,
    
    -- Configuration name (e.g., "Production OpenAI", "Development Ollama")
    name VARCHAR(255) NOT NULL,
    
    -- LLM Provider type
    provider VARCHAR(50) NOT NULL CHECK (provider IN (
        'openai',           -- OpenAI API
        'azure_openai',     -- Azure OpenAI
        'ollama',           -- Ollama local models
        'anthropic',        -- Anthropic Claude
        'gemini',           -- Google Gemini
        'bedrock',          -- AWS Bedrock
        'huggingface',      -- HuggingFace
        'openai_compatible' -- Any OpenAI-compatible API
    )),
    
    -- Encrypted API key (using pgcrypto)
    -- NULL for local providers like Ollama
    api_key_encrypted BYTEA,
    
    -- Model configuration
    model_name VARCHAR(255) NOT NULL,              -- e.g., "gpt-4", "claude-3-opus", "llama2"
    base_url VARCHAR(500),                         -- Custom base URL for API
    
    -- Generation parameters
    temperature DECIMAL(3,2) DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INTEGER DEFAULT 4000 CHECK (max_tokens > 0),
    top_p DECIMAL(3,2) DEFAULT 1.0 CHECK (top_p >= 0 AND top_p <= 1),
    
    -- Embedding configuration (optional, can use different model for embeddings)
    embedding_model VARCHAR(255),                  -- e.g., "text-embedding-3-small"
    embedding_base_url VARCHAR(500),
    embedding_api_key_encrypted BYTEA,
    
    -- Additional configuration (JSON for provider-specific settings)
    additional_config JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_default BOOLEAN NOT NULL DEFAULT false,     -- Default config for this project
    
    -- Audit fields
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP
);

-- Ensure only one default config per project (partial unique index)
CREATE UNIQUE INDEX unique_default_per_project 
    ON lightrag_llm_configs(project_id, is_default) 
    WHERE is_default = true;

-- Index for fast lookups
CREATE INDEX idx_llm_config_project_name ON lightrag_llm_configs(project_id, name);
CREATE INDEX idx_llm_configs_user ON lightrag_llm_configs(user_id);
CREATE INDEX idx_llm_configs_project ON lightrag_llm_configs(project_id);
CREATE INDEX idx_llm_configs_active ON lightrag_llm_configs(project_id, is_active);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_llm_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER llm_config_updated_at
    BEFORE UPDATE ON lightrag_llm_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_llm_config_timestamp();

-- Helper functions for encryption/decryption
-- Note: In production, use a secure key management system
-- For now, we'll use an environment variable-based key

-- Function to encrypt API key
CREATE OR REPLACE FUNCTION encrypt_api_key(api_key TEXT, encryption_key TEXT)
RETURNS BYTEA AS $$
BEGIN
    IF api_key IS NULL OR api_key = '' THEN
        RETURN NULL;
    END IF;
    RETURN pgp_sym_encrypt(api_key, encryption_key);
END;
$$ LANGUAGE plpgsql;

-- Function to decrypt API key
CREATE OR REPLACE FUNCTION decrypt_api_key(encrypted_key BYTEA, encryption_key TEXT)
RETURNS TEXT AS $$
BEGIN
    IF encrypted_key IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN pgp_sym_decrypt(encrypted_key, encryption_key);
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON lightrag_llm_configs TO lightrag;
GRANT EXECUTE ON FUNCTION encrypt_api_key(TEXT, TEXT) TO lightrag;
GRANT EXECUTE ON FUNCTION decrypt_api_key(BYTEA, TEXT) TO lightrag;

-- Example usage comments:
/*
-- Insert a new OpenAI configuration
INSERT INTO lightrag_llm_configs (
    user_id, tenant_id, project_id, name, provider, 
    api_key_encrypted, model_name, is_default
) VALUES (
    'user-uuid',
    'tenant-uuid', 
    'project-uuid',
    'Production OpenAI',
    'openai',
    encrypt_api_key('sk-...', 'your-encryption-key'),
    'gpt-4-turbo-preview',
    true
);

-- Insert an Ollama configuration (no API key needed)
INSERT INTO lightrag_llm_configs (
    user_id, tenant_id, project_id, name, provider,
    model_name, base_url, is_default
) VALUES (
    'user-uuid',
    'tenant-uuid',
    'project-uuid', 
    'Local Llama',
    'ollama',
    'llama2',
    'http://localhost:11434',
    false
);

-- Retrieve configuration with decrypted API key
SELECT 
    id, name, provider, model_name,
    decrypt_api_key(api_key_encrypted, 'your-encryption-key') as api_key,
    base_url, temperature, max_tokens
FROM lightrag_llm_configs
WHERE project_id = 'project-uuid' AND is_default = true;
*/
