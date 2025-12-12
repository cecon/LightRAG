"""
Project Management Service
Handles tenants, projects, members, and invitations
"""

import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from lightrag.utils import logger
from lightrag.api.models.auth_models import (
    UserRole,
    InvitationStatus,
    TenantResponse,
    ProjectResponse,
    ProjectMemberResponse,
    InvitationResponse,
    UserProjectsResponse,
)


class ProjectService:
    """Service for managing tenants, projects, and members"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def create_tenant(
        self,
        tenant_id: str,
        name: str,
        owner_id: str,
        description: Optional[str] = None
    ) -> TenantResponse:
        """Create a new tenant"""
        # Check if tenant exists
        existing = await self.db.fetchrow(
            "SELECT id FROM lightrag_tenants WHERE id = $1",
            tenant_id
        )
        if existing:
            raise ValueError(f"Tenant '{tenant_id}' already exists")
        
        # Insert tenant
        await self.db.execute(
            """
            INSERT INTO lightrag_tenants (id, name, description, owner_id)
            VALUES ($1, $2, $3, $4)
            """,
            tenant_id, name, description, owner_id
        )
        
        tenant = await self.get_tenant(tenant_id)
        logger.info(f"Tenant created: {tenant_id} by user {owner_id}")
        return tenant
    
    async def create_project(
        self,
        project_id: str,
        tenant_id: str,
        name: str,
        user_id: str,
        description: Optional[str] = None
    ) -> ProjectResponse:
        """
        Create a new project
        User must be tenant owner or admin
        """
        # Check if user has permission in tenant
        tenant = await self.get_tenant(tenant_id)
        if tenant.owner_id != user_id:
            # Check if user is admin in any project of this tenant
            is_admin = await self.db.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM lightrag_project_members
                    WHERE tenant_id = $1 AND user_id = $2 AND role IN ('owner', 'admin')
                )
                """,
                tenant_id, user_id
            )
            if not is_admin:
                raise PermissionError("User does not have permission to create projects in this tenant")
        
        # Check if project exists
        existing = await self.db.fetchrow(
            "SELECT id FROM lightrag_projects WHERE id = $1",
            project_id
        )
        if existing:
            raise ValueError(f"Project '{project_id}' already exists")
        
        # Insert project
        await self.db.execute(
            """
            INSERT INTO lightrag_projects (id, tenant_id, name, description, created_by)
            VALUES ($1, $2, $3, $4, $5)
            """,
            project_id, tenant_id, name, description, user_id
        )
        
        # Add creator as owner
        await self.db.execute(
            """
            INSERT INTO lightrag_project_members (project_id, tenant_id, user_id, role)
            VALUES ($1, $2, $3, $4)
            """,
            project_id, tenant_id, user_id, UserRole.OWNER.value
        )
        
        project = await self.get_project(project_id, user_id)
        logger.info(f"Project created: {project_id} in tenant {tenant_id}")
        return project
    
    async def get_tenant(self, tenant_id: str) -> TenantResponse:
        """Get tenant by ID"""
        row = await self.db.fetchrow(
            """
            SELECT id, name, description, owner_id, is_active, created_at
            FROM lightrag_tenants
            WHERE id = $1
            """,
            tenant_id
        )
        
        if not row:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        
        return TenantResponse(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            owner_id=str(row['owner_id']),
            is_active=row['is_active'],
            created_at=row['created_at']
        )
    
    async def get_project(self, project_id: str, user_id: str) -> ProjectResponse:
        """Get project by ID with user's role"""
        row = await self.db.fetchrow(
            """
            SELECT p.id, p.tenant_id, p.name, p.description, p.created_by,
                   p.is_active, p.created_at,
                   pm.role as user_role,
                   (SELECT COUNT(*) FROM lightrag_project_members WHERE project_id = p.id) as member_count
            FROM lightrag_projects p
            LEFT JOIN lightrag_project_members pm ON pm.project_id = p.id AND pm.user_id = $2
            WHERE p.id = $1
            """,
            project_id, user_id
        )
        
        if not row:
            raise ValueError(f"Project '{project_id}' not found")
        
        return ProjectResponse(
            id=row['id'],
            tenant_id=row['tenant_id'],
            name=row['name'],
            description=row['description'],
            created_by=str(row['created_by']),
            is_active=row['is_active'],
            created_at=row['created_at'],
            member_count=row['member_count'],
            user_role=UserRole(row['user_role']) if row['user_role'] else None
        )
    
    async def get_user_projects(self, user_id: str) -> UserProjectsResponse:
        """Get all projects accessible to a user"""
        # Get tenants where user is owner
        tenant_rows = await self.db.fetch(
            """
            SELECT id, name, description, owner_id, is_active, created_at
            FROM lightrag_tenants
            WHERE owner_id = $1 OR id IN (
                SELECT DISTINCT tenant_id
                FROM lightrag_project_members
                WHERE user_id = $1
            )
            ORDER BY created_at DESC
            """,
            user_id
        )
        
        tenants = [
            TenantResponse(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                owner_id=str(row['owner_id']),
                is_active=row['is_active'],
                created_at=row['created_at']
            )
            for row in tenant_rows
        ]
        
        # Get projects where user is member
        project_rows = await self.db.fetch(
            """
            SELECT p.id, p.tenant_id, p.name, p.description, p.created_by,
                   p.is_active, p.created_at,
                   pm.role as user_role,
                   (SELECT COUNT(*) FROM lightrag_project_members WHERE project_id = p.id) as member_count
            FROM lightrag_projects p
            JOIN lightrag_project_members pm ON pm.project_id = p.id
            WHERE pm.user_id = $1
            ORDER BY p.created_at DESC
            """,
            user_id
        )
        
        projects = [
            ProjectResponse(
                id=row['id'],
                tenant_id=row['tenant_id'],
                name=row['name'],
                description=row['description'],
                created_by=str(row['created_by']),
                is_active=row['is_active'],
                created_at=row['created_at'],
                member_count=row['member_count'],
                user_role=UserRole(row['user_role'])
            )
            for row in project_rows
        ]
        
        return UserProjectsResponse(tenants=tenants, projects=projects)
    
    async def invite_member(
        self,
        project_id: str,
        email: str,
        role: UserRole,
        invited_by: str
    ) -> InvitationResponse:
        """
        Invite a user to a project
        Inviter must be owner or admin
        """
        # Check inviter permission
        inviter_role = await self.db.fetchval(
            "SELECT role FROM lightrag_project_members WHERE project_id = $1 AND user_id = $2",
            project_id, invited_by
        )
        
        if inviter_role not in [UserRole.OWNER.value, UserRole.ADMIN.value]:
            raise PermissionError("Only owners and admins can invite members")
        
        # Get project details
        project = await self.db.fetchrow(
            "SELECT tenant_id FROM lightrag_projects WHERE id = $1",
            project_id
        )
        if not project:
            raise ValueError("Project not found")
        
        # Check if user is already a member
        existing_member = await self.db.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM lightrag_project_members pm
                JOIN lightrag_users u ON u.id = pm.user_id
                WHERE pm.project_id = $1 AND u.email = $2
            )
            """,
            project_id, email
        )
        
        if existing_member:
            raise ValueError("User is already a member of this project")
        
        # Check for pending invitation
        existing_invitation = await self.db.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM lightrag_invitations
                WHERE project_id = $1 AND email = $2 AND status = 'pending'
            )
            """,
            project_id, email
        )
        
        if existing_invitation:
            raise ValueError("User already has a pending invitation")
        
        # Create invitation
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        invitation_id = await self.db.fetchval(
            """
            INSERT INTO lightrag_invitations (
                project_id, tenant_id, email, role, invited_by, token, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            project_id, project['tenant_id'], email, role.value,
            invited_by, token, expires_at
        )
        
        invitation = await self.get_invitation(invitation_id)
        logger.info(f"User invited to project {project_id}: {email}")
        return invitation
    
    async def accept_invitation(self, token: str, user_id: str) -> ProjectResponse:
        """Accept a project invitation"""
        # Get invitation
        invitation = await self.db.fetchrow(
            """
            SELECT id, project_id, tenant_id, email, role, expires_at, status
            FROM lightrag_invitations
            WHERE token = $1
            """,
            token
        )
        
        if not invitation:
            raise ValueError("Invalid invitation token")
        
        if invitation['status'] != InvitationStatus.PENDING.value:
            raise ValueError(f"Invitation is {invitation['status']}")
        
        if invitation['expires_at'] < datetime.utcnow():
            await self.db.execute(
                "UPDATE lightrag_invitations SET status = $1 WHERE id = $2",
                InvitationStatus.EXPIRED.value, invitation['id']
            )
            raise ValueError("Invitation has expired")
        
        # Verify user email matches invitation
        user_email = await self.db.fetchval(
            "SELECT email FROM lightrag_users WHERE id = $1",
            user_id
        )
        
        if user_email != invitation['email']:
            raise ValueError("This invitation is for a different email address")
        
        # Add user to project
        await self.db.execute(
            """
            INSERT INTO lightrag_project_members (project_id, tenant_id, user_id, role)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (project_id, user_id) DO NOTHING
            """,
            invitation['project_id'], invitation['tenant_id'],
            user_id, invitation['role']
        )
        
        # Mark invitation as accepted
        await self.db.execute(
            """
            UPDATE lightrag_invitations
            SET status = $1, accepted_at = $2, accepted_by = $3
            WHERE id = $4
            """,
            InvitationStatus.ACCEPTED.value, datetime.utcnow(),
            user_id, invitation['id']
        )
        
        project = await self.get_project(invitation['project_id'], user_id)
        logger.info(f"Invitation accepted: user {user_id} joined project {invitation['project_id']}")
        return project
    
    async def get_invitation(self, invitation_id: str) -> InvitationResponse:
        """Get invitation by ID"""
        row = await self.db.fetchrow(
            """
            SELECT id, project_id, tenant_id, email, role, invited_by,
                   expires_at, status, created_at
            FROM lightrag_invitations
            WHERE id = $1
            """,
            invitation_id
        )
        
        if not row:
            raise ValueError("Invitation not found")
        
        return InvitationResponse(
            id=str(row['id']),
            project_id=row['project_id'],
            tenant_id=row['tenant_id'],
            email=row['email'],
            role=UserRole(row['role']),
            invited_by=str(row['invited_by']),
            expires_at=row['expires_at'],
            status=InvitationStatus(row['status']),
            created_at=row['created_at']
        )
    
    async def get_project_members(self, project_id: str) -> List[ProjectMemberResponse]:
        """Get all members of a project"""
        rows = await self.db.fetch(
            """
            SELECT pm.id, pm.user_id, pm.role, pm.joined_at,
                   u.email, u.name
            FROM lightrag_project_members pm
            JOIN lightrag_users u ON u.id = pm.user_id
            WHERE pm.project_id = $1
            ORDER BY pm.joined_at
            """,
            project_id
        )
        
        return [
            ProjectMemberResponse(
                id=str(row['id']),
                user_id=str(row['user_id']),
                user_email=row['email'],
                user_name=row['name'],
                role=UserRole(row['role']),
                joined_at=row['joined_at']
            )
            for row in rows
        ]
    
    async def check_user_access(
        self,
        user_id: str,
        tenant_id: str,
        project_id: str
    ) -> Optional[UserRole]:
        """
        Check if user has access to a project
        Returns user's role or None
        """
        role = await self.db.fetchval(
            """
            SELECT role FROM lightrag_project_members
            WHERE user_id = $1 AND tenant_id = $2 AND project_id = $3
            """,
            user_id, tenant_id, project_id
        )
        
        return UserRole(role) if role else None
    
    async def update_member_role(
        self,
        project_id: str,
        target_user_id: str,
        new_role: UserRole,
        updated_by: str
    ) -> ProjectMemberResponse:
        """
        Update a member's role
        Only owners can change roles
        """
        # Check updater permission
        updater_role = await self.db.fetchval(
            "SELECT role FROM lightrag_project_members WHERE project_id = $1 AND user_id = $2",
            project_id, updated_by
        )
        
        if updater_role != UserRole.OWNER.value:
            raise PermissionError("Only owners can update member roles")
        
        # Update role
        await self.db.execute(
            "UPDATE lightrag_project_members SET role = $1 WHERE project_id = $2 AND user_id = $3",
            new_role.value, project_id, target_user_id
        )
        
        # Get updated member
        row = await self.db.fetchrow(
            """
            SELECT pm.id, pm.user_id, pm.role, pm.joined_at,
                   u.email, u.name
            FROM lightrag_project_members pm
            JOIN lightrag_users u ON u.id = pm.user_id
            WHERE pm.project_id = $1 AND pm.user_id = $2
            """,
            project_id, target_user_id
        )
        
        logger.info(f"Member role updated in project {project_id}: user {target_user_id} -> {new_role.value}")
        
        return ProjectMemberResponse(
            id=str(row['id']),
            user_id=str(row['user_id']),
            user_email=row['email'],
            user_name=row['name'],
            role=UserRole(row['role']),
            joined_at=row['joined_at']
        )
    
    async def remove_member(
        self,
        project_id: str,
        target_user_id: str,
        removed_by: str
    ):
        """
        Remove a member from a project
        Only owners can remove members
        Cannot remove the last owner
        """
        # Check remover permission
        remover_role = await self.db.fetchval(
            "SELECT role FROM lightrag_project_members WHERE project_id = $1 AND user_id = $2",
            project_id, removed_by
        )
        
        if remover_role != UserRole.OWNER.value:
            raise PermissionError("Only owners can remove members")
        
        # Check if target is last owner
        target_role = await self.db.fetchval(
            "SELECT role FROM lightrag_project_members WHERE project_id = $1 AND user_id = $2",
            project_id, target_user_id
        )
        
        if target_role == UserRole.OWNER.value:
            owner_count = await self.db.fetchval(
                "SELECT COUNT(*) FROM lightrag_project_members WHERE project_id = $1 AND role = $2",
                project_id, UserRole.OWNER.value
            )
            if owner_count <= 1:
                raise ValueError("Cannot remove the last owner")
        
        # Remove member
        await self.db.execute(
            "DELETE FROM lightrag_project_members WHERE project_id = $1 AND user_id = $2",
            project_id, target_user_id
        )
        
        logger.info(f"Member removed from project {project_id}: user {target_user_id}")
