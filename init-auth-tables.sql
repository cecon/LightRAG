-- Authentication and Multi-Tenant User Management Tables
-- This script creates tables for user authentication, tenant/project management, and access control

-- Users table: stores user accounts
CREATE TABLE IF NOT EXISTS lightrag_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    email_verification_token VARCHAR(255),
    email_verification_expires_at TIMESTAMPTZ,
    password_reset_token VARCHAR(255),
    password_reset_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ
);

-- Tenants table: represents organizations/companies
CREATE TABLE IF NOT EXISTS lightrag_tenants (
    id VARCHAR(255) PRIMARY KEY,  -- tenant_id usado no sistema
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE RESTRICT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Projects table: projects within tenants
CREATE TABLE IF NOT EXISTS lightrag_projects (
    id VARCHAR(255) NOT NULL,  -- project_id usado no sistema
    tenant_id VARCHAR(255) NOT NULL REFERENCES lightrag_tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE RESTRICT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (id)  -- project_id deve ser único globalmente
);

-- Project members: users that have access to projects
CREATE TABLE IF NOT EXISTS lightrag_project_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL REFERENCES lightrag_projects(id) ON DELETE CASCADE,
    tenant_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',  -- owner, admin, member, viewer
    invited_by UUID REFERENCES lightrag_users(id) ON DELETE SET NULL,
    joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, user_id),
    FOREIGN KEY (tenant_id, project_id) REFERENCES lightrag_projects(tenant_id, id) ON DELETE CASCADE
);

-- Invitations: pending project invitations
CREATE TABLE IF NOT EXISTS lightrag_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL REFERENCES lightrag_projects(id) ON DELETE CASCADE,
    tenant_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    invited_by UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    accepted_by UUID REFERENCES lightrag_users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, accepted, expired, cancelled
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id, project_id) REFERENCES lightrag_projects(tenant_id, id) ON DELETE CASCADE
);

-- Refresh tokens for JWT authentication
CREATE TABLE IF NOT EXISTS lightrag_refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES lightrag_users(id) ON DELETE CASCADE,
    token VARCHAR(500) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    replaced_by UUID REFERENCES lightrag_refresh_tokens(id) ON DELETE SET NULL
);

-- Audit log for important actions
CREATE TABLE IF NOT EXISTS lightrag_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES lightrag_users(id) ON DELETE SET NULL,
    tenant_id VARCHAR(255),
    project_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON lightrag_users(email);
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON lightrag_users(email_verification_token);
CREATE INDEX IF NOT EXISTS idx_users_reset_token ON lightrag_users(password_reset_token);
CREATE INDEX IF NOT EXISTS idx_tenants_owner ON lightrag_tenants(owner_id);
CREATE INDEX IF NOT EXISTS idx_projects_tenant ON lightrag_projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_created_by ON lightrag_projects(created_by);
CREATE INDEX IF NOT EXISTS idx_project_members_user ON lightrag_project_members(user_id);
CREATE INDEX IF NOT EXISTS idx_project_members_project ON lightrag_project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON lightrag_invitations(email);
CREATE INDEX IF NOT EXISTS idx_invitations_token ON lightrag_invitations(token);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON lightrag_invitations(status);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON lightrag_refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON lightrag_refresh_tokens(token);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON lightrag_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON lightrag_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON lightrag_audit_log(created_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON lightrag_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON lightrag_tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON lightrag_projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lightrag;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO lightrag;
