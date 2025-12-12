"""
Authentication Service
Handles user authentication, registration, and token management
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
import bcrypt
import jwt
from lightrag.utils import logger
from lightrag.api.models.auth_models import (
    UserDB,
    UserResponse,
    AuthTokenResponse,
)


class AuthService:
    """Service for handling authentication operations"""
    
    def __init__(
        self,
        db_connection,
        secret_key: str,
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 30,
    ):
        self.db = db_connection
        self.secret_key = secret_key
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.algorithm = "HS256"
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )
    
    def create_access_token(self, user_id: str, email: str) -> str:
        """Create a JWT access token"""
        expires = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expires,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self) -> str:
        """Create a secure random refresh token"""
        return secrets.token_urlsafe(64)
    
    def decode_access_token(self, token: str) -> Optional[dict]:
        """Decode and verify an access token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            if payload.get("type") != "access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Access token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid access token: {e}")
            return None
    
    async def register_user(
        self,
        email: str,
        password: str,
        name: str,
        phone: Optional[str] = None
    ) -> Tuple[UserResponse, str]:
        """
        Register a new user
        
        Returns:
            Tuple of (user_response, verification_token)
        """
        # Check if user exists
        existing = await self.db.fetchrow(
            "SELECT id FROM lightrag_users WHERE email = $1",
            email
        )
        if existing:
            raise ValueError("Email already registered")
        
        # Hash password
        password_hash = self.hash_password(password)
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(days=7)
        
        # Insert user
        user_id = await self.db.fetchval(
            """
            INSERT INTO lightrag_users (
                email, password_hash, name, phone,
                email_verification_token, email_verification_expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            email, password_hash, name, phone,
            verification_token, verification_expires
        )
        
        # Fetch created user
        user = await self.get_user_by_id(user_id)
        
        logger.info(f"User registered: {email}")
        return user, verification_token
    
    async def login_user(self, email: str, password: str) -> AuthTokenResponse:
        """
        Authenticate user and return tokens
        
        Raises:
            ValueError: If credentials are invalid
        """
        # Get user
        row = await self.db.fetchrow(
            """
            SELECT id, email, password_hash, name, phone, is_active, is_verified,
                   created_at, last_login_at
            FROM lightrag_users
            WHERE email = $1
            """,
            email
        )
        
        if not row:
            raise ValueError("Invalid email or password")
        
        # Verify password
        if not self.verify_password(password, row['password_hash']):
            raise ValueError("Invalid email or password")
        
        # Check if active
        if not row['is_active']:
            raise ValueError("Account is inactive")
        
        # Create tokens
        access_token = self.create_access_token(str(row['id']), row['email'])
        refresh_token = self.create_refresh_token()
        
        # Store refresh token
        refresh_expires = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        await self.db.execute(
            """
            INSERT INTO lightrag_refresh_tokens (user_id, token, expires_at)
            VALUES ($1, $2, $3)
            """,
            row['id'], refresh_token, refresh_expires
        )
        
        # Update last login
        await self.db.execute(
            "UPDATE lightrag_users SET last_login_at = $1 WHERE id = $2",
            datetime.utcnow(), row['id']
        )
        
        # Build response
        user = UserResponse(
            id=str(row['id']),
            email=row['email'],
            name=row['name'],
            phone=row['phone'],
            is_active=row['is_active'],
            is_verified=row['is_verified'],
            created_at=row['created_at'],
            last_login_at=datetime.utcnow()
        )
        
        logger.info(f"User logged in: {email}")
        
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60,
            user=user
        )
    
    async def verify_email(self, token: str) -> bool:
        """Verify user email with token"""
        row = await self.db.fetchrow(
            """
            SELECT id FROM lightrag_users
            WHERE email_verification_token = $1
              AND email_verification_expires_at > $2
              AND is_verified = false
            """,
            token, datetime.utcnow()
        )
        
        if not row:
            return False
        
        await self.db.execute(
            """
            UPDATE lightrag_users
            SET is_verified = true,
                email_verification_token = NULL,
                email_verification_expires_at = NULL
            WHERE id = $1
            """,
            row['id']
        )
        
        logger.info(f"Email verified for user: {row['id']}")
        return True
    
    async def request_password_reset(self, email: str) -> Optional[str]:
        """Request password reset and return token if user exists"""
        # Check if user exists
        user_id = await self.db.fetchval(
            "SELECT id FROM lightrag_users WHERE email = $1 AND is_active = true",
            email
        )
        
        if not user_id:
            # Don't reveal if email exists
            return None
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        reset_expires = datetime.utcnow() + timedelta(hours=2)
        
        await self.db.execute(
            """
            UPDATE lightrag_users
            SET password_reset_token = $1,
                password_reset_expires_at = $2
            WHERE id = $3
            """,
            reset_token, reset_expires, user_id
        )
        
        logger.info(f"Password reset requested for: {email}")
        return reset_token
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password with token"""
        row = await self.db.fetchrow(
            """
            SELECT id FROM lightrag_users
            WHERE password_reset_token = $1
              AND password_reset_expires_at > $2
            """,
            token, datetime.utcnow()
        )
        
        if not row:
            return False
        
        # Hash new password
        password_hash = self.hash_password(new_password)
        
        await self.db.execute(
            """
            UPDATE lightrag_users
            SET password_hash = $1,
                password_reset_token = NULL,
                password_reset_expires_at = NULL
            WHERE id = $2
            """,
            password_hash, row['id']
        )
        
        # Revoke all refresh tokens for security
        await self.db.execute(
            "UPDATE lightrag_refresh_tokens SET revoked_at = $1 WHERE user_id = $2",
            datetime.utcnow(), row['id']
        )
        
        logger.info(f"Password reset for user: {row['id']}")
        return True
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[AuthTokenResponse]:
        """Refresh access token using refresh token"""
        row = await self.db.fetchrow(
            """
            SELECT rt.id, rt.user_id, u.email, u.name, u.phone, u.is_active, u.is_verified,
                   u.created_at, u.last_login_at
            FROM lightrag_refresh_tokens rt
            JOIN lightrag_users u ON u.id = rt.user_id
            WHERE rt.token = $1
              AND rt.expires_at > $2
              AND rt.revoked_at IS NULL
            """,
            refresh_token, datetime.utcnow()
        )
        
        if not row:
            return None
        
        # Create new tokens
        access_token = self.create_access_token(str(row['user_id']), row['email'])
        new_refresh_token = self.create_refresh_token()
        
        # Store new refresh token
        refresh_expires = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        new_token_id = await self.db.fetchval(
            """
            INSERT INTO lightrag_refresh_tokens (user_id, token, expires_at)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            row['user_id'], new_refresh_token, refresh_expires
        )
        
        # Revoke old refresh token
        await self.db.execute(
            "UPDATE lightrag_refresh_tokens SET revoked_at = $1, replaced_by = $2 WHERE id = $3",
            datetime.utcnow(), new_token_id, row['id']
        )
        
        # Build response
        user = UserResponse(
            id=str(row['user_id']),
            email=row['email'],
            name=row['name'],
            phone=row['phone'],
            is_active=row['is_active'],
            is_verified=row['is_verified'],
            created_at=row['created_at'],
            last_login_at=row['last_login_at']
        )
        
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self.access_token_expire_minutes * 60,
            user=user
        )
    
    async def get_user_by_id(self, user_id: str) -> UserResponse:
        """Get user by ID"""
        row = await self.db.fetchrow(
            """
            SELECT id, email, name, phone, is_active, is_verified, created_at, last_login_at
            FROM lightrag_users
            WHERE id = $1
            """,
            user_id
        )
        
        if not row:
            raise ValueError("User not found")
        
        return UserResponse(
            id=str(row['id']),
            email=row['email'],
            name=row['name'],
            phone=row['phone'],
            is_active=row['is_active'],
            is_verified=row['is_verified'],
            created_at=row['created_at'],
            last_login_at=row['last_login_at']
        )
    
    async def logout(self, refresh_token: str):
        """Logout user by revoking refresh token"""
        await self.db.execute(
            "UPDATE lightrag_refresh_tokens SET revoked_at = $1 WHERE token = $2",
            datetime.utcnow(), refresh_token
        )
