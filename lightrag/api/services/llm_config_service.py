"""
LLM Configuration Service
Handles CRUD operations for LLM provider configurations per user/project
Manages encryption/decryption of API keys
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncpg
from lightrag.api.models.auth_models import (
    LLMProvider,
    LLMConfigRequest,
    LLMConfigResponse,
    LLMConfigUpdateRequest,
)
from lightrag.utils import logger


class LLMConfigService:
    """Service for managing LLM configurations"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        # Get encryption key from environment (should be 32+ chars)
        self.encryption_key = os.getenv("LLM_CONFIG_ENCRYPTION_KEY", "change-this-to-secure-key-min-32-chars")
        if len(self.encryption_key) < 32:
            logger.warning("LLM_CONFIG_ENCRYPTION_KEY should be at least 32 characters!")
    
    async def create_config(
        self,
        user_id: str,
        request: LLMConfigRequest
    ) -> LLMConfigResponse:
        """
        Create a new LLM configuration for a project
        
        Args:
            user_id: ID of the user creating the config
            request: LLM configuration request
            
        Returns:
            Created LLM configuration
            
        Raises:
            PermissionError: If user doesn't have access to project
            ValueError: If configuration already exists or invalid
        """
        async with self.db_pool.acquire() as conn:
            # Verify user has access to the project
            access_check = await conn.fetchval(
                """
                SELECT role FROM lightrag_project_members
                WHERE user_id = $1 AND project_id = $2
                """,
                user_id, request.project_id
            )
            
            if not access_check:
                raise PermissionError("You don't have access to this project")
            
            # Get tenant_id from project
            tenant_id = await conn.fetchval(
                "SELECT tenant_id FROM lightrag_projects WHERE id = $1",
                request.project_id
            )
            
            if not tenant_id:
                raise ValueError("Project not found")
            
            # Check if config with this name already exists for this project
            existing = await conn.fetchval(
                "SELECT id FROM lightrag_llm_configs WHERE project_id = $1 AND name = $2",
                request.project_id, request.name
            )
            
            if existing:
                raise ValueError(f"Configuration '{request.name}' already exists for this project")
            
            # If setting as default, unset other defaults
            if request.is_default:
                await conn.execute(
                    "UPDATE lightrag_llm_configs SET is_default = false WHERE project_id = $1",
                    request.project_id
                )
            
            # Encrypt API keys if provided
            api_key_encrypted = None
            if request.api_key:
                api_key_encrypted = await conn.fetchval(
                    "SELECT encrypt_api_key($1, $2)",
                    request.api_key, self.encryption_key
                )
            
            embedding_key_encrypted = None
            if request.embedding_api_key:
                embedding_key_encrypted = await conn.fetchval(
                    "SELECT encrypt_api_key($1, $2)",
                    request.embedding_api_key, self.encryption_key
                )
            
            # Convert additional_config dict to JSON string
            import json
            additional_config_json = json.dumps(request.additional_config) if request.additional_config else None
            
            # Insert configuration
            config_id = await conn.fetchval(
                """
                INSERT INTO lightrag_llm_configs (
                    user_id, tenant_id, project_id, name, provider,
                    api_key_encrypted, model_name, base_url,
                    temperature, max_tokens, top_p,
                    embedding_model, embedding_base_url, embedding_api_key_encrypted,
                    additional_config, is_default
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
                """,
                user_id, tenant_id, request.project_id, request.name, request.provider.value,
                api_key_encrypted, request.model_name, request.base_url,
                request.temperature, request.max_tokens, request.top_p,
                request.embedding_model, request.embedding_base_url, embedding_key_encrypted,
                additional_config_json, request.is_default
            )
            
            # Return the created config (without API keys)
            return await self.get_config_by_id(config_id)
    
    async def get_config_by_id(self, config_id: str) -> LLMConfigResponse:
        """Get LLM configuration by ID (without decrypted API keys)"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    id, user_id, tenant_id, project_id, name, provider,
                    model_name, base_url, temperature, max_tokens, top_p,
                    embedding_model, embedding_base_url,
                    additional_config, is_active, is_default,
                    created_at, updated_at, last_used_at,
                    api_key_encrypted IS NOT NULL as has_api_key,
                    embedding_api_key_encrypted IS NOT NULL as has_embedding_api_key
                FROM lightrag_llm_configs
                WHERE id = $1
                """,
                config_id
            )
            
            if not row:
                raise ValueError(f"Configuration {config_id} not found")
            
            return LLMConfigResponse(
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                tenant_id=str(row["tenant_id"]),
                project_id=str(row["project_id"]),
                name=row["name"],
                provider=LLMProvider(row["provider"]),
                model_name=row["model_name"],
                base_url=row["base_url"],
                temperature=float(row["temperature"]),
                max_tokens=row["max_tokens"],
                top_p=float(row["top_p"]),
                embedding_model=row["embedding_model"],
                embedding_base_url=row["embedding_base_url"],
                has_embedding_api_key=row["has_embedding_api_key"],
                additional_config=row["additional_config"] or {},
                is_active=row["is_active"],
                is_default=row["is_default"],
                has_api_key=row["has_api_key"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_used_at=row["last_used_at"]
            )
    
    async def get_decrypted_config(self, config_id: str) -> Dict[str, Any]:
        """
        Get LLM configuration with decrypted API keys
        Used internally by instance_manager to configure LightRAG
        
        Returns:
            Dictionary with all config including decrypted API keys
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    id, user_id, tenant_id, project_id, name, provider,
                    decrypt_api_key(api_key_encrypted, $2) as api_key,
                    model_name, base_url, temperature, max_tokens, top_p,
                    embedding_model, embedding_base_url,
                    decrypt_api_key(embedding_api_key_encrypted, $2) as embedding_api_key,
                    additional_config
                FROM lightrag_llm_configs
                WHERE id = $1 AND is_active = true
                """,
                config_id, self.encryption_key
            )
            
            if not row:
                raise ValueError(f"Active configuration {config_id} not found")
            
            return dict(row)
    
    async def get_project_configs(
        self,
        user_id: str,
        project_id: str
    ) -> List[LLMConfigResponse]:
        """
        Get all LLM configurations for a project
        
        Args:
            user_id: User ID (for permission check)
            project_id: Project ID
            
        Returns:
            List of LLM configurations
        """
        async with self.db_pool.acquire() as conn:
            # Verify user has access
            access = await conn.fetchval(
                "SELECT role FROM lightrag_project_members WHERE user_id = $1 AND project_id = $2",
                user_id, project_id
            )
            
            if not access:
                raise PermissionError("You don't have access to this project")
            
            rows = await conn.fetch(
                """
                SELECT 
                    id, user_id, tenant_id, project_id, name, provider,
                    model_name, base_url, temperature, max_tokens, top_p,
                    embedding_model, embedding_base_url,
                    additional_config, is_active, is_default,
                    created_at, updated_at, last_used_at,
                    api_key_encrypted IS NOT NULL as has_api_key,
                    embedding_api_key_encrypted IS NOT NULL as has_embedding_api_key
                FROM lightrag_llm_configs
                WHERE project_id = $1
                ORDER BY is_default DESC, created_at DESC
                """,
                project_id
            )
            
            return [
                LLMConfigResponse(
                    id=str(row["id"]),
                    user_id=str(row["user_id"]),
                    tenant_id=str(row["tenant_id"]),
                    project_id=str(row["project_id"]),
                    name=row["name"],
                    provider=LLMProvider(row["provider"]),
                    model_name=row["model_name"],
                    base_url=row["base_url"],
                    temperature=float(row["temperature"]),
                    max_tokens=row["max_tokens"],
                    top_p=float(row["top_p"]),
                    embedding_model=row["embedding_model"],
                    embedding_base_url=row["embedding_base_url"],
                    has_embedding_api_key=row["has_embedding_api_key"],
                    additional_config=row["additional_config"] or {},
                    is_active=row["is_active"],
                    is_default=row["is_default"],
                    has_api_key=row["has_api_key"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_used_at=row["last_used_at"]
                )
                for row in rows
            ]
    
    async def get_default_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get default LLM configuration for a project (with decrypted keys)
        Used by instance_manager
        
        Returns:
            Decrypted configuration dict or None if no default set
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    id, provider,
                    decrypt_api_key(api_key_encrypted, $2) as api_key,
                    model_name, base_url, temperature, max_tokens, top_p,
                    embedding_model, embedding_base_url,
                    decrypt_api_key(embedding_api_key_encrypted, $2) as embedding_api_key,
                    additional_config
                FROM lightrag_llm_configs
                WHERE project_id = $1 AND is_default = true AND is_active = true
                """,
                project_id, self.encryption_key
            )
            
            if row:
                # Update last_used_at
                await conn.execute(
                    "UPDATE lightrag_llm_configs SET last_used_at = NOW() WHERE id = $1",
                    row["id"]
                )
                return dict(row)
            
            return None
    
    async def update_config(
        self,
        user_id: str,
        config_id: str,
        request: LLMConfigUpdateRequest
    ) -> LLMConfigResponse:
        """
        Update LLM configuration
        
        Args:
            user_id: User ID (for permission check)
            config_id: Configuration ID
            request: Update request
            
        Returns:
            Updated configuration
        """
        async with self.db_pool.acquire() as conn:
            # Get current config to check permissions
            current = await conn.fetchrow(
                "SELECT project_id, is_default FROM lightrag_llm_configs WHERE id = $1",
                config_id
            )
            
            if not current:
                raise ValueError("Configuration not found")
            
            # Verify user has access
            access = await conn.fetchval(
                "SELECT role FROM lightrag_project_members WHERE user_id = $1 AND project_id = $2",
                user_id, current["project_id"]
            )
            
            if not access:
                raise PermissionError("You don't have access to this project")
            
            # Build update query dynamically
            updates = []
            params = []
            param_idx = 1
            
            if request.name is not None:
                updates.append(f"name = ${param_idx}")
                params.append(request.name)
                param_idx += 1
            
            if request.api_key is not None:
                # Re-encrypt API key
                encrypted = await conn.fetchval(
                    "SELECT encrypt_api_key($1, $2)",
                    request.api_key, self.encryption_key
                )
                updates.append(f"api_key_encrypted = ${param_idx}")
                params.append(encrypted)
                param_idx += 1
            
            if request.base_url is not None:
                updates.append(f"base_url = ${param_idx}")
                params.append(request.base_url)
                param_idx += 1
            
            if request.model_name is not None:
                updates.append(f"model_name = ${param_idx}")
                params.append(request.model_name)
                param_idx += 1
            
            if request.temperature is not None:
                updates.append(f"temperature = ${param_idx}")
                params.append(request.temperature)
                param_idx += 1
            
            if request.max_tokens is not None:
                updates.append(f"max_tokens = ${param_idx}")
                params.append(request.max_tokens)
                param_idx += 1
            
            if request.top_p is not None:
                updates.append(f"top_p = ${param_idx}")
                params.append(request.top_p)
                param_idx += 1
            
            if request.embedding_model is not None:
                updates.append(f"embedding_model = ${param_idx}")
                params.append(request.embedding_model)
                param_idx += 1
            
            if request.embedding_base_url is not None:
                updates.append(f"embedding_base_url = ${param_idx}")
                params.append(request.embedding_base_url)
                param_idx += 1
            
            if request.embedding_api_key is not None:
                encrypted = await conn.fetchval(
                    "SELECT encrypt_api_key($1, $2)",
                    request.embedding_api_key, self.encryption_key
                )
                updates.append(f"embedding_api_key_encrypted = ${param_idx}")
                params.append(encrypted)
                param_idx += 1
            
            if request.additional_config is not None:
                import json
                updates.append(f"additional_config = ${param_idx}")
                params.append(json.dumps(request.additional_config))
                param_idx += 1
            
            if request.is_active is not None:
                updates.append(f"is_active = ${param_idx}")
                params.append(request.is_active)
                param_idx += 1
            
            if request.is_default is not None:
                # If setting as default, unset others
                if request.is_default:
                    await conn.execute(
                        "UPDATE lightrag_llm_configs SET is_default = false WHERE project_id = $1",
                        current["project_id"]
                    )
                updates.append(f"is_default = ${param_idx}")
                params.append(request.is_default)
                param_idx += 1
            
            if not updates:
                # No updates requested, return current config
                return await self.get_config_by_id(config_id)
            
            # Execute update
            params.append(config_id)
            query = f"""
                UPDATE lightrag_llm_configs
                SET {', '.join(updates)}
                WHERE id = ${param_idx}
            """
            
            await conn.execute(query, *params)
            
            return await self.get_config_by_id(config_id)
    
    async def delete_config(self, user_id: str, config_id: str):
        """
        Delete LLM configuration
        
        Args:
            user_id: User ID (for permission check)
            config_id: Configuration ID
        """
        async with self.db_pool.acquire() as conn:
            # Get config to check permissions
            project_id = await conn.fetchval(
                "SELECT project_id FROM lightrag_llm_configs WHERE id = $1",
                config_id
            )
            
            if not project_id:
                raise ValueError("Configuration not found")
            
            # Verify user has access
            access = await conn.fetchval(
                "SELECT role FROM lightrag_project_members WHERE user_id = $1 AND project_id = $2",
                user_id, project_id
            )
            
            if not access:
                raise PermissionError("You don't have access to this project")
            
            # Delete configuration
            await conn.execute(
                "DELETE FROM lightrag_llm_configs WHERE id = $1",
                config_id
            )
