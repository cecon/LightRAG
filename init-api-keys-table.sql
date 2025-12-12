-- API Keys Table for programmatic access
-- Separate from JWT tokens used for web panel authentication

CREATE TABLE IF NOT EXISTS lightrag_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE CASCADE,
    tenant_id VARCHAR(255) REFERENCES lightrag_tenants(id) ON DELETE CASCADE,
    project_id VARCHAR(255) REFERENCES lightrag_projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,  -- User-friendly name for the key
    key_prefix VARCHAR(20) NOT NULL,  -- First chars for identification (e.g., "lrag_abc...")
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- bcrypt hash of the full key
    scopes JSONB DEFAULT '[]'::jsonb,  -- Permissions: ["query", "insert", "delete", "admin"]
    last_used_at TIMESTAMPTZ,
    last_used_ip INET,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,  -- Optional expiration
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES lightrag_users(id) ON DELETE SET NULL,
    CONSTRAINT fk_project FOREIGN KEY (tenant_id, project_id) 
        REFERENCES lightrag_projects(tenant_id, id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON lightrag_api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_project ON lightrag_api_keys(project_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON lightrag_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON lightrag_api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON lightrag_api_keys(is_active) WHERE is_active = true;

-- Trigger for updated_at
CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON lightrag_api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON lightrag_api_keys TO lightrag;
