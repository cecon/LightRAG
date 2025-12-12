"""
API Key Management Routes
Handles creation and management of API keys for programmatic access
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from lightrag.api.models.auth_models import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
)
from lightrag.api.services.api_key_service import APIKeyService
from lightrag.utils import logger


router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def get_api_key_service(request: Request) -> APIKeyService:
    """Dependency to get API key service from app state"""
    return request.app.state.api_key_service


def get_current_user_id(request: Request) -> str:
    """Get current user ID from JWT token"""
    # Check if already authenticated
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return user_id
    
    # Validate token directly
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.replace("Bearer ", "")
    
    # Only JWT tokens allowed for API key management (not API keys themselves)
    if token.startswith("lrag_"):
        raise HTTPException(status_code=401, detail="API keys cannot manage API keys. Use JWT token from login.")
    
    # Validate JWT token
    auth_service = request.app.state.auth_service
    payload = auth_service.decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Store in request state
    request.state.user_id = user_id
    request.state.user_email = payload.get("email")
    request.state.auth_type = "jwt"
    
    return user_id


@router.post("/", response_model=APIKeyCreateResponse)
async def create_api_key(
    data: APIKeyCreateRequest,
    user_id: str = Depends(get_current_user_id),
    api_key_service: APIKeyService = Depends(get_api_key_service)
):
    """
    Create a new API key for programmatic access.
    
    **Important:** The full API key is shown only once in the response.
    Save it immediately - you won't be able to retrieve it again!
    
    **Authentication:** Requires JWT Bearer token (from login).
    
    **Use cases:**
    - Integrate LightRAG with your application
    - Create scripts/bots that query your knowledge base
    - Build custom frontends
    
    **Scopes:**
    - `query`: Read and query documents
    - `insert`: Insert and update documents
    - `delete`: Delete documents
    - `admin`: Full access including member management
    
    **Example usage of API key:**
    ```bash
    curl -X POST http://localhost:9621/query/data \\
      -H "Authorization: Bearer lrag_your_api_key_here" \\
      -H "Content-Type: application/json" \\
      -d '{"query": "What is RAG?", "mode": "hybrid"}'
    ```
    
    Returns:
        APIKeyCreateResponse: The created API key with full key (shown only once)
    """
    try:
        api_key = await api_key_service.create_api_key(
            user_id=user_id,
            project_id=data.project_id,
            name=data.name,
            scopes=data.scopes,
            expires_at=data.expires_at
        )
        return api_key
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Create API key error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/", response_model=List[APIKeyResponse])
async def list_api_keys(
    project_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    api_key_service: APIKeyService = Depends(get_api_key_service)
):
    """
    List all API keys created by the current user.
    
    Optionally filter by project_id.
    
    **Note:** The full API key is never shown in this list.
    Only the key prefix (first 12 characters) is displayed for identification.
    
    Returns:
        List[APIKeyResponse]: List of API keys (without full keys)
    """
    try:
        keys = await api_key_service.list_user_api_keys(
            user_id=user_id,
            project_id=project_id
        )
        return keys
    
    except Exception as e:
        logger.error(f"List API keys error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    api_key_service: APIKeyService = Depends(get_api_key_service)
):
    """
    Revoke an API key.
    
    The key will be immediately deactivated and can no longer be used.
    This action cannot be undone.
    
    Returns:
        Success message
    """
    try:
        await api_key_service.revoke_api_key(
            key_id=key_id,
            user_id=user_id
        )
        return {"message": "API key revoked successfully"}
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Revoke API key error: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.delete("/{key_id}/permanent")
async def delete_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    api_key_service: APIKeyService = Depends(get_api_key_service)
):
    """
    Permanently delete an API key.
    
    This removes the key from the database completely.
    This action cannot be undone.
    
    Returns:
        Success message
    """
    try:
        await api_key_service.delete_api_key(
            key_id=key_id,
            user_id=user_id
        )
        return {"message": "API key deleted successfully"}
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Delete API key error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete API key")
