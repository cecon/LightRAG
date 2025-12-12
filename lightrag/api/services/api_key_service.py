"""
API Key Service
Manages API keys for programmatic access to LightRAG
"""

import secrets
import bcrypt
from datetime import datetime
from typing import List, Optional, Tuple
from lightrag.utils import logger
from lightrag.api.models.auth_models import (
    APIKeyResponse,
    APIKeyCreateResponse,
    APIKeyScope,
)


class APIKeyService:
    """Service for managing API keys"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def generate_api_key(self) -> Tuple[str, str, str]:
        """
        Generate a new API key.
        
        Returns:
            Tuple of (full_key, key_prefix, key_hash)
            - full_key: The complete key to show to user (only once)
            - key_prefix: First characters for identification
            - key_hash: bcrypt hash to store in database
        """
        # Generate random key: lrag_<32 random chars>
        random_part = secrets.token_urlsafe(32)
        full_key = f"lrag_{random_part}"
        
        # Get prefix for display (first 12 chars)
        key_prefix = full_key[:12] + "..."
        
        # Hash the key for storage
        key_hash = bcrypt.hashpw(
            full_key.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
        
        return full_key, key_prefix, key_hash
    
    def verify_api_key(self, key: str, key_hash: str) -> bool:
        """Verify an API key against its hash"""
        return bcrypt.checkpw(
            key.encode('utf-8'),
            key_hash.encode('utf-8')
        )
    
    async def create_api_key(
        self,
        user_id: str,
        project_id: str,
        name: str,
        scopes: List[APIKeyScope],
        expires_at: Optional[datetime] = None
    ) -> APIKeyCreateResponse:
        """
        Create a new API key for a project.
        
        User must have access to the project.
        Returns the full key only once!
        """
        # Get project details
        project = await self.db.fetchrow(
            "SELECT tenant_id FROM lightrag_projects WHERE id = $1",
            project_id
        )
        
        if not project:
            raise ValueError("Project not found")
        
        # Check user has access to project
        has_access = await self.db.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM lightrag_project_members
                WHERE project_id = $1 AND user_id = $2
            )
            """,
            project_id, user_id
        )
        
        if not has_access:
            raise PermissionError("You don't have access to this project")
        
        # Generate key
        full_key, key_prefix, key_hash = self.generate_api_key()
        
        # Convert scopes to list of strings and JSON-encode
        import json
        scope_values = [scope.value for scope in scopes]
        scope_json = json.dumps(scope_values)
        
        # Insert API key
        key_id = await self.db.fetchval(
            """
            INSERT INTO lightrag_api_keys (
                user_id, tenant_id, project_id, name, key_prefix, key_hash,
                scopes, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            user_id, project['tenant_id'], project_id, name,
            key_prefix, key_hash, scope_json, expires_at
        )
        
        # Fetch created key
        row = await self.db.fetchrow(
            """
            SELECT id, name, key_prefix, project_id, tenant_id, scopes,
                   expires_at, created_at
            FROM lightrag_api_keys
            WHERE id = $1
            """,
            key_id
        )
        
        logger.info(f"API key created: {name} for project {project_id}")
        
        # Parse JSON scopes
        import json
        scopes_list = json.loads(row['scopes']) if isinstance(row['scopes'], str) else row['scopes']
        
        return APIKeyCreateResponse(
            id=str(row['id']),
            name=row['name'],
            key=full_key,  # Show full key only here!
            key_prefix=row['key_prefix'],
            project_id=row['project_id'],
            tenant_id=row['tenant_id'],
            scopes=scopes_list,
            expires_at=row['expires_at'],
            created_at=row['created_at']
        )
    
    async def validate_api_key(
        self,
        key: str
    ) -> Optional[dict]:
        """
        Validate an API key and return associated data.
        
        Returns:
            Dict with user_id, tenant_id, project_id, scopes or None if invalid
        """
        # API keys start with "lrag_"
        if not key.startswith("lrag_"):
            return None
        
        # Get all active keys (we need to check hash for each)
        # In production, you might want to add key_prefix index for faster lookup
        rows = await self.db.fetch(
            """
            SELECT id, user_id, tenant_id, project_id, key_hash, scopes,
                   expires_at, is_active
            FROM lightrag_api_keys
            WHERE is_active = true
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > $1)
            """,
            datetime.utcnow()
        )
        
        # Check each key
        import json
        for row in rows:
            if self.verify_api_key(key, row['key_hash']):
                # Update last used
                await self.db.execute(
                    "UPDATE lightrag_api_keys SET last_used_at = $1 WHERE id = $2",
                    datetime.utcnow(), row['id']
                )
                
                # Parse JSON scopes
                scopes_list = json.loads(row['scopes']) if isinstance(row['scopes'], str) else row['scopes']
                
                return {
                    "key_id": str(row['id']),
                    "user_id": str(row['user_id']),
                    "tenant_id": row['tenant_id'],
                    "project_id": row['project_id'],
                    "scopes": scopes_list
                }
        
        return None
    
    async def list_user_api_keys(
        self,
        user_id: str,
        project_id: Optional[str] = None
    ) -> List[APIKeyResponse]:
        """
        List all API keys for a user, optionally filtered by project.
        """
        if project_id:
            rows = await self.db.fetch(
                """
                SELECT id, name, key_prefix, project_id, tenant_id, scopes,
                       is_active, last_used_at, expires_at, created_at
                FROM lightrag_api_keys
                WHERE user_id = $1 AND project_id = $2
                ORDER BY created_at DESC
                """,
                user_id, project_id
            )
        else:
            rows = await self.db.fetch(
                """
                SELECT id, name, key_prefix, project_id, tenant_id, scopes,
                       is_active, last_used_at, expires_at, created_at
                FROM lightrag_api_keys
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id
            )
        
        import json
        return [
            APIKeyResponse(
                id=str(row['id']),
                name=row['name'],
                key_prefix=row['key_prefix'],
                project_id=row['project_id'],
                tenant_id=row['tenant_id'],
                scopes=json.loads(row['scopes']) if isinstance(row['scopes'], str) else row['scopes'],
                is_active=row['is_active'],
                last_used_at=row['last_used_at'],
                expires_at=row['expires_at'],
                created_at=row['created_at']
            )
            for row in rows
        ]
    
    async def revoke_api_key(
        self,
        key_id: str,
        user_id: str
    ) -> bool:
        """
        Revoke an API key.
        User must own the key.
        """
        # Check ownership
        is_owner = await self.db.fetchval(
            "SELECT user_id = $1 FROM lightrag_api_keys WHERE id = $2",
            user_id, key_id
        )
        
        if not is_owner:
            raise PermissionError("You don't own this API key")
        
        # Revoke key
        await self.db.execute(
            """
            UPDATE lightrag_api_keys
            SET is_active = false, revoked_at = $1, revoked_by = $2
            WHERE id = $3
            """,
            datetime.utcnow(), user_id, key_id
        )
        
        logger.info(f"API key revoked: {key_id}")
        return True
    
    async def delete_api_key(
        self,
        key_id: str,
        user_id: str
    ) -> bool:
        """
        Delete an API key permanently.
        User must own the key.
        """
        # Check ownership
        is_owner = await self.db.fetchval(
            "SELECT user_id = $1 FROM lightrag_api_keys WHERE id = $2",
            user_id, key_id
        )
        
        if not is_owner:
            raise PermissionError("You don't own this API key")
        
        # Delete key
        await self.db.execute(
            "DELETE FROM lightrag_api_keys WHERE id = $1",
            key_id
        )
        
        logger.info(f"API key deleted: {key_id}")
        return True
