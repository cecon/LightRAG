"""
Authentication and User Management Models
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum


class UserRole(str, Enum):
    """User roles in a project"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class InvitationStatus(str, Enum):
    """Invitation status"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ===== Request Models =====

class UserRegisterRequest(BaseModel):
    """Request model for user registration"""
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLoginRequest(BaseModel):
    """Request model for user login"""
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Request model for password reset"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token"""
    token: str
    new_password: str = Field(min_length=8, max_length=100)


class EmailVerificationRequest(BaseModel):
    """Request model for email verification"""
    token: str


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh"""
    refresh_token: str


class TenantCreateRequest(BaseModel):
    """Request model for creating a tenant"""
    id: str = Field(min_length=3, max_length=255, pattern=r'^[a-z0-9_-]+$')
    name: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None


class ProjectCreateRequest(BaseModel):
    """Request model for creating a project"""
    id: str = Field(min_length=3, max_length=255, pattern=r'^[a-z0-9_-]+$')
    tenant_id: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None


class InviteMemberRequest(BaseModel):
    """Request model for inviting a member to a project"""
    email: EmailStr
    role: UserRole = UserRole.MEMBER


class AcceptInvitationRequest(BaseModel):
    """Request model for accepting an invitation"""
    token: str


class UpdateMemberRoleRequest(BaseModel):
    """Request model for updating member role"""
    user_id: str
    role: UserRole


# ===== Response Models =====

class UserResponse(BaseModel):
    """Response model for user data"""
    id: str
    email: str
    name: str
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class AuthTokenResponse(BaseModel):
    """Response model for authentication tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class TenantResponse(BaseModel):
    """Response model for tenant data"""
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    is_active: bool
    created_at: datetime


class ProjectResponse(BaseModel):
    """Response model for project data"""
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    created_by: str
    is_active: bool
    created_at: datetime
    member_count: Optional[int] = None
    user_role: Optional[UserRole] = None


class ProjectMemberResponse(BaseModel):
    """Response model for project member"""
    id: str
    user_id: str
    user_email: str
    user_name: str
    role: UserRole
    joined_at: datetime


class InvitationResponse(BaseModel):
    """Response model for invitation"""
    id: str
    project_id: str
    tenant_id: str
    email: str
    role: UserRole
    invited_by: str
    expires_at: datetime
    status: InvitationStatus
    created_at: datetime


class UserProjectsResponse(BaseModel):
    """Response model for user's projects"""
    tenants: List[TenantResponse]
    projects: List[ProjectResponse]


# ===== Database Models =====

class UserDB(BaseModel):
    """Database model for user"""
    id: str
    email: str
    password_hash: str
    name: str
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    email_verification_token: Optional[str]
    email_verification_expires_at: Optional[datetime]
    password_reset_token: Optional[str]
    password_reset_expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]


class TenantDB(BaseModel):
    """Database model for tenant"""
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectDB(BaseModel):
    """Database model for project"""
    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    created_by: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectMemberDB(BaseModel):
    """Database model for project member"""
    id: str
    project_id: str
    tenant_id: str
    user_id: str
    role: str
    invited_by: Optional[str]
    joined_at: datetime
    created_at: datetime


class InvitationDB(BaseModel):
    """Database model for invitation"""
    id: str
    project_id: str
    tenant_id: str
    email: str
    role: str
    invited_by: str
    token: str
    expires_at: datetime
    accepted_at: Optional[datetime]
    accepted_by: Optional[str]
    status: str
    created_at: datetime


class APIKeyScope(str, Enum):
    """API Key scopes/permissions"""
    QUERY = "query"  # Read/query documents
    INSERT = "insert"  # Insert/update documents
    DELETE = "delete"  # Delete documents
    ADMIN = "admin"  # Full access including member management


# ===== API Key Models =====

class APIKeyCreateRequest(BaseModel):
    """Request model for creating an API key"""
    name: str = Field(min_length=2, max_length=255)
    project_id: str
    scopes: List[APIKeyScope] = Field(default=[APIKeyScope.QUERY])
    expires_at: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    """Response model for API key (without the actual key)"""
    id: str
    name: str
    key_prefix: str  # e.g., "lrag_abc..."
    project_id: str
    tenant_id: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime


class APIKeyCreateResponse(BaseModel):
    """Response when creating API key (includes the actual key ONCE)"""
    id: str
    name: str
    key: str  # Full key shown only once!
    key_prefix: str
    project_id: str
    tenant_id: str
    scopes: List[str]
    expires_at: Optional[datetime]
    created_at: datetime
    warning: str = "Save this key now. You won't be able to see it again!"


# ============================================================================
# LLM Configuration Models
# ============================================================================

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    BEDROCK = "bedrock"
    HUGGINGFACE = "huggingface"
    OPENAI_COMPATIBLE = "openai_compatible"


class LLMConfigRequest(BaseModel):
    """Request to create or update LLM configuration"""
    project_id: str
    name: str
    provider: LLMProvider
    
    # API credentials (encrypted in database)
    api_key: Optional[str] = None  # Not needed for local providers like Ollama
    base_url: Optional[str] = None
    
    # Model settings
    model_name: str
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=4000, gt=0)
    top_p: Optional[float] = Field(default=1.0, ge=0, le=1)
    
    # Optional embedding configuration
    embedding_model: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    
    # Additional provider-specific settings
    additional_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Status flags
    is_default: bool = False


class LLMConfigResponse(BaseModel):
    """Response with LLM configuration (API key never exposed)"""
    id: str
    user_id: str
    tenant_id: str
    project_id: str
    name: str
    provider: LLMProvider
    
    # Model settings
    model_name: str
    base_url: Optional[str] = None
    temperature: float
    max_tokens: int
    top_p: float
    
    # Embedding settings
    embedding_model: Optional[str] = None
    embedding_base_url: Optional[str] = None
    has_embedding_api_key: bool = False  # Boolean flag instead of actual key
    
    # Additional config
    additional_config: Dict[str, Any]
    
    # Status
    is_active: bool
    is_default: bool
    has_api_key: bool  # Boolean flag instead of actual key
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None


class LLMConfigUpdateRequest(BaseModel):
    """Request to update existing LLM configuration"""
    name: Optional[str] = None
    api_key: Optional[str] = None  # If provided, will re-encrypt
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    embedding_model: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    additional_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

