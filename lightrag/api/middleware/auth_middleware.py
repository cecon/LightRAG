"""
Authentication Middleware
Validates JWT tokens and adds user information to request state
"""

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from lightrag.utils import logger


security = HTTPBearer(auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT tokens OR API keys and populate request.state with user info
    
    Supports two authentication methods:
    1. JWT Bearer Token (for web panel login) - short-lived
    2. API Key (for programmatic access) - persistent, starts with "lrag_"
    """
    
    def __init__(self, app, auth_service, api_key_service=None):
        super().__init__(app)
        self.auth_service = auth_service
        self.api_key_service = api_key_service
        
        # Paths that don't require authentication
        self.public_paths = {
            "/auth/register",
            "/auth/login",
            "/auth/verify-email",
            "/auth/password-reset/request",
            "/auth/password-reset/confirm",
            "/auth/refresh",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/auth-status",
        }
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for public paths
        if any(request.url.path.startswith(path) for path in self.public_paths):
            return await call_next(request)
        
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            # Allow unauthenticated access, endpoints will check if needed
            return await call_next(request)
        
        try:
            # Extract token/key
            token = auth_header.replace("Bearer ", "")
            
            # Check if it's an API key (starts with "lrag_")
            if token.startswith("lrag_") and self.api_key_service:
                # Validate API key
                api_key_context = await self.api_key_service.validate_api_key(token)
                
                if api_key_context:
                    # Add API key context to request state
                    request.state.user_id = api_key_context["user_id"]
                    request.state.tenant_id = api_key_context["tenant_id"]
                    request.state.project_id = api_key_context["project_id"]
                    request.state.scopes = api_key_context["scopes"]
                    request.state.auth_type = "api_key"
                else:
                    logger.warning(f"Invalid API key: {token[:12]}...")
                    
            else:
                # Validate JWT token
                payload = self.auth_service.decode_access_token(token)
                
                if payload:
                    # Add user info to request state
                    request.state.user_id = payload.get("sub")
                    request.state.user_email = payload.get("email")
                    request.state.auth_type = "jwt"
            
        except Exception as e:
            logger.warning(f"Auth middleware error: {e}")
            # Don't raise error, let endpoints handle missing auth
        
        return await call_next(request)


async def require_auth(request: Request) -> str:
    """
    Dependency that requires authentication.
    Use this in route dependencies to enforce authentication.
    
    Returns:
        str: User ID
        
    Raises:
        HTTPException: If user is not authenticated
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    return user_id


async def require_verified_user(request: Request, auth_service) -> str:
    """
    Dependency that requires verified user.
    
    Returns:
        str: User ID
        
    Raises:
        HTTPException: If user is not authenticated or verified
    """
    user_id = await require_auth(request)
    
    # Check if user is verified
    user = await auth_service.get_user_by_id(user_id)
    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Email verification required"
        )
    
    return user_id


async def check_project_access(
    request: Request,
    tenant_id: str,
    project_id: str,
    project_service,
    required_roles: list = None
):
    """
    Check if user has access to a project with optional role requirement.
    
    Supports both JWT and API key authentication.
    
    Args:
        request: FastAPI Request
        tenant_id: Tenant ID
        project_id: Project ID
        project_service: ProjectService instance
        required_roles: List of required roles (e.g., ['owner', 'admin'])
        
    Returns:
        str: User role in the project (or "api_key" for API key auth)
        
    Raises:
        HTTPException: If user doesn't have access or required role
    """
    auth_type = getattr(request.state, "auth_type", None)
    
    # API Key authentication
    if auth_type == "api_key":
        # Check if the API key is for this project
        api_tenant_id = getattr(request.state, "tenant_id", None)
        api_project_id = getattr(request.state, "project_id", None)
        
        if api_tenant_id != tenant_id or api_project_id != project_id:
            raise HTTPException(
                status_code=403,
                detail="API key is not authorized for this project"
            )
        
        # API keys with admin scope bypass role checks
        scopes = getattr(request.state, "scopes", [])
        if "admin" in scopes:
            return "api_key"
        
        # Otherwise check required roles (API keys are treated as admin for role checks)
        if required_roles and "admin" not in scopes:
            raise HTTPException(
                status_code=403,
                detail=f"This operation requires admin API key scope"
            )
        
        return "api_key"
    
    # JWT authentication
    user_id = await require_auth(request)
    
    # Check user access
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
    
    # Check role requirement
    if required_roles and user_role.value not in required_roles:
        raise HTTPException(
            status_code=403,
            detail=f"This operation requires one of these roles: {', '.join(required_roles)}"
        )
    
    return user_role


async def require_scope(request: Request, required_scope: str):
    """
    Dependency to check if API key has required scope.
    Only applies to API key authentication.
    
    Args:
        request: FastAPI Request
        required_scope: Required scope (e.g., "query", "insert", "delete", "admin")
        
    Raises:
        HTTPException: If API key doesn't have required scope
    """
    auth_type = getattr(request.state, "auth_type", None)
    
    # Only check scope for API key auth
    if auth_type == "api_key":
        scopes = getattr(request.state, "scopes", [])
        
        # Admin scope grants all permissions
        if "admin" in scopes or required_scope in scopes:
            return
        
        raise HTTPException(
            status_code=403,
            detail=f"API key requires '{required_scope}' scope for this operation"
        )
