"""
LLM Configuration Routes
Handles creation and management of LLM provider configurations
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from lightrag.api.models.auth_models import (
    LLMConfigRequest,
    LLMConfigResponse,
    LLMConfigUpdateRequest,
)
from lightrag.api.services.llm_config_service import LLMConfigService
from lightrag.utils import logger


router = APIRouter(prefix="/llm-configs", tags=["llm-configs"])


def get_llm_config_service(request: Request) -> LLMConfigService:
    """Dependency to get LLM config service from app state"""
    return request.app.state.llm_config_service


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
    
    # Check if it's an API key
    if token.startswith("lrag_"):
        api_key_service = request.app.state.api_key_service
        import asyncio
        loop = asyncio.get_event_loop()
        api_key_context = loop.run_until_complete(api_key_service.validate_api_key(token))
        
        if not api_key_context:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        request.state.user_id = api_key_context["user_id"]
        request.state.tenant_id = api_key_context.get("tenant_id")
        request.state.project_id = api_key_context.get("project_id")
        request.state.scopes = api_key_context.get("scopes", [])
        request.state.auth_type = "api_key"
        
        return api_key_context["user_id"]
    
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


@router.post("/", response_model=LLMConfigResponse)
async def create_llm_config(
    data: LLMConfigRequest,
    user_id: str = Depends(get_current_user_id),
    llm_service: LLMConfigService = Depends(get_llm_config_service)
):
    """
    Create a new LLM configuration for a project.
    
    **Authentication:** Requires JWT Bearer token.
    
    This allows each project to have its own LLM provider settings:
    - API keys (encrypted in database)
    - Model selection
    - Temperature and other parameters
    - Embedding model configuration
    
    **Providers supported:**
    - `openai`: OpenAI API (gpt-4, gpt-3.5-turbo, etc.)
    - `azure_openai`: Azure OpenAI Service
    - `ollama`: Ollama local models (no API key needed)
    - `anthropic`: Anthropic Claude
    - `gemini`: Google Gemini
    - `bedrock`: AWS Bedrock
    - `huggingface`: HuggingFace
    - `openai_compatible`: Any OpenAI-compatible API
    
    **Example: OpenAI Configuration**
    ```json
    {
      "project_id": "proj-uuid",
      "name": "Production OpenAI",
      "provider": "openai",
      "api_key": "sk-...",
      "model_name": "gpt-4-turbo-preview",
      "temperature": 0.7,
      "max_tokens": 4000,
      "is_default": true
    }
    ```
    
    **Example: Ollama Configuration (local)**
    ```json
    {
      "project_id": "proj-uuid",
      "name": "Local Llama",
      "provider": "ollama",
      "model_name": "llama2",
      "base_url": "http://localhost:11434",
      "temperature": 0.7,
      "is_default": false
    }
    ```
    
    **Security:** API keys are encrypted using pgcrypto before storage.
    
    Returns:
        LLMConfigResponse: The created configuration (API key not exposed)
    """
    try:
        config = await llm_service.create_config(
            user_id=user_id,
            request=data
        )
        return config
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create LLM config error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create LLM configuration")


@router.get("/project/{project_id}", response_model=List[LLMConfigResponse])
async def list_project_llm_configs(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    llm_service: LLMConfigService = Depends(get_llm_config_service)
):
    """
    List all LLM configurations for a project.
    
    Returns configurations ordered by:
    1. Default configuration first
    2. Then by creation date (newest first)
    
    **Note:** API keys are never exposed in the response.
    Only a boolean flag `has_api_key` indicates if a key is set.
    
    Returns:
        List[LLMConfigResponse]: List of LLM configurations
    """
    try:
        configs = await llm_service.get_project_configs(
            user_id=user_id,
            project_id=project_id
        )
        return configs
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"List LLM configs error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list LLM configurations")


@router.get("/{config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    config_id: str,
    llm_service: LLMConfigService = Depends(get_llm_config_service)
):
    """
    Get a specific LLM configuration by ID.
    
    **Note:** API keys are not exposed. Use this for displaying config details.
    
    Returns:
        LLMConfigResponse: The configuration (without API keys)
    """
    try:
        config = await llm_service.get_config_by_id(config_id)
        return config
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Get LLM config error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get LLM configuration")


@router.put("/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: str,
    data: LLMConfigUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    llm_service: LLMConfigService = Depends(get_llm_config_service)
):
    """
    Update an existing LLM configuration.
    
    You can update any field including:
    - API key (will be re-encrypted)
    - Model name
    - Temperature and other parameters
    - Default status
    - Active status
    
    **Example: Update API key and model**
    ```json
    {
      "api_key": "sk-new-key...",
      "model_name": "gpt-4-turbo"
    }
    ```
    
    **Example: Set as default**
    ```json
    {
      "is_default": true
    }
    ```
    
    Returns:
        LLMConfigResponse: The updated configuration
    """
    try:
        config = await llm_service.update_config(
            user_id=user_id,
            config_id=config_id,
            request=data
        )
        return config
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Update LLM config error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update LLM configuration")


@router.delete("/{config_id}")
async def delete_llm_config(
    config_id: str,
    user_id: str = Depends(get_current_user_id),
    llm_service: LLMConfigService = Depends(get_llm_config_service)
):
    """
    Delete an LLM configuration.
    
    **Warning:** This action cannot be undone.
    
    If you delete the default configuration, you'll need to set
    another one as default or create a new one.
    
    Returns:
        Success message
    """
    try:
        await llm_service.delete_config(
            user_id=user_id,
            config_id=config_id
        )
        return {"message": "LLM configuration deleted successfully"}
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Delete LLM config error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete LLM configuration")
