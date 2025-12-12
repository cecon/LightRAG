"""
Project Management Routes
Handles tenants, projects, members, and invitations
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from lightrag.api.models.auth_models import (
    TenantCreateRequest,
    ProjectCreateRequest,
    InviteMemberRequest,
    AcceptInvitationRequest,
    UpdateMemberRoleRequest,
    TenantResponse,
    ProjectResponse,
    ProjectMemberResponse,
    InvitationResponse,
    UserProjectsResponse,
)
from lightrag.api.services.project_service import ProjectService
from lightrag.utils import logger


router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(request: Request) -> ProjectService:
    """Dependency to get project service from app state"""
    return request.app.state.project_service


def get_current_user_id(request: Request) -> str:
    """
    Dependency to get current user ID from request.
    Requires valid access token in Authorization header.
    """
    # Check if already authenticated by middleware
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return user_id
    
    # If not, validate token directly
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.replace("Bearer ", "")
    
    # Check if it's an API key
    if token.startswith("lrag_"):
        api_key_service = request.app.state.api_key_service
        api_key_context = None
        
        import asyncio
        if asyncio.iscoroutinefunction(api_key_service.validate_api_key):
            # Run async function synchronously in dependency
            import asyncio
            loop = asyncio.get_event_loop()
            api_key_context = loop.run_until_complete(api_key_service.validate_api_key(token))
        else:
            api_key_context = api_key_service.validate_api_key(token)
        
        if not api_key_context:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Store in request state for other uses
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


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    data: TenantCreateRequest,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Create a new tenant (organization).
    
    The user creating the tenant becomes its owner.
    Tenant ID must be unique and follow naming conventions.
    
    Returns:
        TenantResponse: Created tenant information
    """
    try:
        tenant = await project_service.create_tenant(
            tenant_id=data.id,
            name=data.name,
            owner_id=user_id,
            description=data.description
        )
        return tenant
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create tenant error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tenant")


@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreateRequest,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Create a new project within a tenant.
    
    User must be the tenant owner or have admin role in the tenant.
    The user creating the project becomes its owner.
    
    Returns:
        ProjectResponse: Created project information
    """
    try:
        project = await project_service.create_project(
            project_id=data.id,
            tenant_id=data.tenant_id,
            name=data.name,
            user_id=user_id,
            description=data.description
        )
        return project
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.get("/my", response_model=UserProjectsResponse)
async def get_my_projects(
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Get all projects accessible to the current user.
    
    Returns both tenants and projects the user is a member of.
    Projects include the user's role and member count.
    
    Returns:
        UserProjectsResponse: Tenants and projects accessible to user
    """
    try:
        projects = await project_service.get_user_projects(user_id)
        return projects
    
    except Exception as e:
        logger.error(f"Get user projects error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get projects")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Get project details.
    
    Returns project information including user's role and member count.
    
    Returns:
        ProjectResponse: Project information
    """
    try:
        project = await project_service.get_project(project_id, user_id)
        
        # Check if user has access
        if project.user_role is None:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this project"
            )
        
        return project
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project")


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
async def get_project_members(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Get all members of a project.
    
    User must have access to the project.
    
    Returns:
        List[ProjectMemberResponse]: Project members with their roles
    """
    try:
        # Check user access
        project = await project_service.get_project(project_id, user_id)
        if project.user_role is None:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this project"
            )
        
        members = await project_service.get_project_members(project_id)
        return members
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project members error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get members")


@router.post("/{project_id}/invite", response_model=InvitationResponse)
async def invite_member(
    project_id: str,
    data: InviteMemberRequest,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Invite a user to join a project.
    
    Only project owners and admins can invite members.
    An invitation email will be sent to the specified address.
    
    Returns:
        InvitationResponse: Created invitation information
    """
    try:
        invitation = await project_service.invite_member(
            project_id=project_id,
            email=data.email,
            role=data.role,
            invited_by=user_id
        )
        
        # TODO: Send invitation email
        logger.info(f"Invitation created: {invitation.id}")
        
        return invitation
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Invite member error: {e}")
        raise HTTPException(status_code=500, detail="Failed to invite member")


@router.post("/invitations/accept", response_model=ProjectResponse)
async def accept_invitation(
    data: AcceptInvitationRequest,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Accept a project invitation.
    
    Token is sent via email. User's email must match the invitation.
    After accepting, user becomes a project member.
    
    Returns:
        ProjectResponse: Project information user joined
    """
    try:
        project = await project_service.accept_invitation(
            token=data.token,
            user_id=user_id
        )
        return project
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Accept invitation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to accept invitation")


@router.put("/{project_id}/members/{target_user_id}/role", response_model=ProjectMemberResponse)
async def update_member_role(
    project_id: str,
    target_user_id: str,
    data: UpdateMemberRoleRequest,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Update a project member's role.
    
    Only project owners can update roles.
    
    Returns:
        ProjectMemberResponse: Updated member information
    """
    try:
        member = await project_service.update_member_role(
            project_id=project_id,
            target_user_id=target_user_id,
            new_role=data.role,
            updated_by=user_id
        )
        return member
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Update member role error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update role")


@router.delete("/{project_id}/members/{target_user_id}")
async def remove_member(
    project_id: str,
    target_user_id: str,
    user_id: str = Depends(get_current_user_id),
    project_service: ProjectService = Depends(get_project_service)
):
    """
    Remove a member from a project.
    
    Only project owners can remove members.
    Cannot remove the last owner.
    
    Returns:
        Success message
    """
    try:
        await project_service.remove_member(
            project_id=project_id,
            target_user_id=target_user_id,
            removed_by=user_id
        )
        return {"message": "Member removed successfully"}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Remove member error: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove member")
