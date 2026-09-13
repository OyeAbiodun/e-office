"""Project persistence boundary."""

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.modules.projects.models import Project, ProjectMember
from meetinghq_api.modules.users.models import User


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        project: Project | None = await self.session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
                Project.deleted_at.is_(None),
            )
        )
        return project

    def visible_query(self, actor: User, can_view_all: bool) -> Select[tuple[Project]]:
        query = select(Project).where(
            Project.organization_id == actor.organization_id,
            Project.deleted_at.is_(None),
        )
        if can_view_all:
            return query
        membership = select(ProjectMember.project_id).where(
            ProjectMember.organization_id == actor.organization_id,
            ProjectMember.user_id == actor.id,
        )
        clauses = [
            Project.project_manager_id == actor.id,
            Project.id.in_(membership),
            Project.visibility == "organization",
        ]
        if actor.department_id:
            clauses.append(
                (Project.visibility == "department")
                & (Project.department_id == actor.department_id)
            )
        return query.where(or_(*clauses))

    async def next_sequence(self, organization_id: uuid.UUID) -> int:
        return (
            int(
                await self.session.scalar(
                    select(func.coalesce(func.max(Project.sequence), 0)).where(
                        Project.organization_id == organization_id
                    )
                )
                or 0
            )
            + 1
        )
