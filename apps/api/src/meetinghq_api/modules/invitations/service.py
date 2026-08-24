"""Invitation application service."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.core.config import Settings
from meetinghq_api.core.errors import AuthenticationError
from meetinghq_api.infrastructure.events import TransactionalDomainEventPublisher
from meetinghq_api.modules.auth.infrastructure.email import IdentityEmailSender
from meetinghq_api.modules.auth.infrastructure.passwords import hash_password
from meetinghq_api.modules.auth.infrastructure.tokens import create_opaque_token, hash_token
from meetinghq_api.modules.invitations.models import Invitation, InvitationStatus
from meetinghq_api.modules.users.models import Role, User, UserStatus
from meetinghq_api.shared.events import DomainEvent, DomainEventPublisher
from meetinghq_api.shared.exceptions import ConflictError, NotFoundError


class InvitationService:
    """Tenant-safe invitation lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        events: DomainEventPublisher | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.events = events or TransactionalDomainEventPublisher(session)
        self.email = IdentityEmailSender(session, settings)

    async def list(self, organization_id: uuid.UUID) -> list[Invitation]:
        invitations = list(
            (
                await self.session.scalars(
                    select(Invitation)
                    .where(Invitation.organization_id == organization_id)
                    .order_by(Invitation.created_at.desc())
                )
            ).all()
        )
        now = datetime.now(UTC)
        for invitation in invitations:
            if (
                invitation.status == InvitationStatus.PENDING
                and invitation.expires_at.replace(tzinfo=UTC) <= now
            ):
                invitation.status = InvitationStatus.EXPIRED
        return invitations

    async def invite(
        self, organization_id: uuid.UUID, email: str, role_name: str, actor_id: uuid.UUID
    ) -> Invitation:
        normalized = email.lower()
        if await self.session.scalar(
            select(User.id).where(User.organization_id == organization_id, User.email == normalized)
        ):
            raise ConflictError("User already belongs to the organization")
        pending = await self.session.scalar(
            select(Invitation).where(
                Invitation.organization_id == organization_id,
                Invitation.email == normalized,
                Invitation.status == InvitationStatus.PENDING,
            )
        )
        if pending:
            raise ConflictError("A pending invitation already exists")
        if (
            await self.session.scalar(
                select(Role.id).where(
                    Role.organization_id == organization_id, Role.name == role_name
                )
            )
            is None
        ):
            raise NotFoundError("Role not found")
        raw_token = create_opaque_token()
        invitation = Invitation(
            organization_id=organization_id,
            email=normalized,
            role_name=role_name,
            token_hash=hash_token(raw_token),
            invited_by_id=actor_id,
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.invitation_ttl_days),
        )
        self.session.add(invitation)
        await self.session.flush()
        await self.email.send_invitation(normalized, raw_token, organization_id)
        await self.events.publish(
            DomainEvent(
                name="UserInvited",
                organization_id=organization_id,
                actor_id=actor_id,
                aggregate_type="invitation",
                aggregate_id=invitation.id,
                payload={"role": role_name, "email": normalized},
            )
        )
        return invitation

    async def resend(self, organization_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
        invitation = await self._get(organization_id, invitation_id)
        if invitation.status not in {
            InvitationStatus.PENDING,
            InvitationStatus.EXPIRED,
        }:
            raise ConflictError("Invitation cannot be resent")
        raw_token = create_opaque_token()
        invitation.token_hash = hash_token(raw_token)
        invitation.status = InvitationStatus.PENDING
        invitation.resend_count += 1
        invitation.expires_at = datetime.now(UTC) + timedelta(
            days=self.settings.invitation_ttl_days
        )
        await self.email.send_invitation(invitation.email, raw_token, invitation.organization_id)
        return invitation

    async def cancel(self, organization_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        invitation = await self._get(organization_id, invitation_id)
        if invitation.status != InvitationStatus.PENDING:
            raise ConflictError("Only pending invitations can be cancelled")
        invitation.status = InvitationStatus.CANCELLED
        invitation.cancelled_at = datetime.now(UTC)

    async def accept(
        self,
        raw_token: str,
        username: str,
        first_name: str,
        last_name: str,
        password: str,
    ) -> User:
        invitation = await self.session.scalar(
            select(Invitation).where(Invitation.token_hash == hash_token(raw_token))
        )
        now = datetime.now(UTC)
        if (
            invitation is None
            or invitation.status != InvitationStatus.PENDING
            or invitation.expires_at.replace(tzinfo=UTC) <= now
        ):
            raise AuthenticationError("Invitation is invalid or expired")
        if await self.session.scalar(
            select(User.id).where(
                User.organization_id == invitation.organization_id,
                User.email == invitation.email,
            )
        ):
            raise ConflictError("User already belongs to the organization")
        role = await self.session.scalar(
            select(Role).where(
                Role.organization_id == invitation.organization_id,
                Role.name == invitation.role_name,
            )
        )
        if role is None:
            raise NotFoundError("Invitation role no longer exists")
        user = User(
            organization_id=invitation.organization_id,
            email=invitation.email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            display_name=f"{first_name} {last_name}".strip(),
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=[role],
        )
        self.session.add(user)
        await self.session.flush()
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = now
        invitation.accepted_by_id = user.id
        await self.events.publish(
            DomainEvent(
                name="InvitationAccepted",
                organization_id=user.organization_id,
                actor_id=user.id,
                aggregate_type="user",
                aggregate_id=user.id,
            )
        )
        return user

    async def _get(self, organization_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
        invitation = await self.session.scalar(
            select(Invitation).where(
                Invitation.id == invitation_id,
                Invitation.organization_id == organization_id,
            )
        )
        if invitation is None:
            raise NotFoundError("Invitation not found")
        return invitation
