"""
Authentication Routes
Handles user registration, login, and token management
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from lightrag.api.models.auth_models import (
    UserRegisterRequest,
    UserLoginRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerificationRequest,
    RefreshTokenRequest,
    AuthTokenResponse,
    UserResponse,
)
from lightrag.api.services.auth_service import AuthService
from lightrag.utils import logger


router = APIRouter(prefix="/auth", tags=["authentication"])


def get_auth_service(request: Request) -> AuthService:
    """Dependency to get auth service from app state"""
    return request.app.state.auth_service


@router.post("/register", response_model=UserResponse)
async def register(
    data: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user account.
    
    Creates a new user and sends a verification email.
    User must verify email before accessing protected resources.
    
    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    
    Returns:
        UserResponse: Created user information
    """
    try:
        user, verification_token = await auth_service.register_user(
            email=data.email,
            password=data.password,
            name=data.name,
            phone=data.phone
        )
        
        # TODO: Send verification email with token
        logger.info(f"User registered: {data.email}, verification_token: {verification_token}")
        
        return user
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    data: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Authenticate user and return access tokens.
    
    Returns both access token (short-lived) and refresh token (long-lived).
    Access token should be included in Authorization header for protected endpoints.
    
    Returns:
        AuthTokenResponse: Authentication tokens and user information
    """
    try:
        auth_response = await auth_service.login_user(
            email=data.email,
            password=data.password
        )
        return auth_response
    
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/verify-email")
async def verify_email(
    data: EmailVerificationRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Verify user email address with token.
    
    Token is sent to user's email during registration.
    Email verification is required for certain operations.
    
    Returns:
        Success message
    """
    try:
        success = await auth_service.verify_email(data.token)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired verification token"
            )
        
        return {"message": "Email verified successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(status_code=500, detail="Email verification failed")


@router.post("/password-reset/request")
async def request_password_reset(
    data: PasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Request password reset for an email address.
    
    Sends a password reset token to the user's email if account exists.
    For security, always returns success even if email doesn't exist.
    
    Returns:
        Success message
    """
    try:
        token = await auth_service.request_password_reset(data.email)
        
        # TODO: Send password reset email with token
        if token:
            logger.info(f"Password reset requested for: {data.email}, token: {token}")
        
        # Always return success to avoid email enumeration
        return {
            "message": "If the email exists, a password reset link has been sent"
        }
    
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        # Still return success to avoid revealing if email exists
        return {
            "message": "If the email exists, a password reset link has been sent"
        }


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    data: PasswordResetConfirm,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Reset password using reset token.
    
    Token is sent to user's email via password reset request.
    All existing sessions will be invalidated after password reset.
    
    Returns:
        Success message
    """
    try:
        success = await auth_service.reset_password(
            token=data.token,
            new_password=data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset token"
            )
        
        return {"message": "Password reset successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(status_code=500, detail="Password reset failed")


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Refresh access token using refresh token.
    
    When access token expires, use this endpoint with refresh token
    to get a new access token without requiring login.
    
    Old refresh token is revoked and a new one is issued.
    
    Returns:
        AuthTokenResponse: New authentication tokens
    """
    try:
        auth_response = await auth_service.refresh_access_token(data.refresh_token)
        
        if not auth_response:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired refresh token"
            )
        
        return auth_response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@router.post("/logout")
async def logout(
    data: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Logout user by revoking refresh token.
    
    After logout, the refresh token can no longer be used.
    Access token will still be valid until it expires.
    
    Returns:
        Success message
    """
    try:
        await auth_service.logout(data.refresh_token)
        return {"message": "Logged out successfully"}
    
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")
