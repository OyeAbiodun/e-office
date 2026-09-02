"""Integration Center endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.domain.permissions import Permissions
from meetinghq_api.modules.auth.presentation.dependencies import require_permission
from meetinghq_api.modules.integrations.schemas import (
    EmailTemplatePreviewResponse,
    IntegrationAuditResponse,
    IntegrationConfigurationUpdate,
    IntegrationOperationResponse,
    IntegrationResponse,
    IntegrationTestResponse,
    SmtpConfigurationResponse,
    SmtpConfigurationUpdate,
    SmtpTestEmailRequest,
    SmtpTestEmailResponse,
)
from meetinghq_api.modules.integrations.service import IntegrationService
from meetinghq_api.modules.notifications.email_templates import TemplateKey
from meetinghq_api.modules.users.models import User

router = APIRouter(prefix="/integrations", tags=["integration-center"])
Session = Annotated[AsyncSession, Depends(get_database_session)]
IntegrationReader = Annotated[User, require_permission(Permissions.INTEGRATIONS_READ)]
IntegrationManager = Annotated[User, require_permission(Permissions.INTEGRATIONS_MANAGE)]
IntegrationTester = Annotated[User, require_permission(Permissions.INTEGRATIONS_TEST)]


def _audit_int(metadata: dict[str, object], key: str) -> int | None:
    value = metadata.get(key)
    return int(value) if isinstance(value, (int, float)) else None


@router.get("", response_model=list[IntegrationResponse])
async def integrations(session: Session, user: IntegrationReader) -> list[IntegrationResponse]:
    return await IntegrationService(session).list(user.organization_id)


@router.get("/smtp/configuration", response_model=SmtpConfigurationResponse)
async def smtp_configuration(
    session: Session, user: IntegrationReader
) -> SmtpConfigurationResponse:
    return await IntegrationService(session).smtp_configuration(user.organization_id)


@router.put("/smtp/configuration", response_model=SmtpConfigurationResponse)
async def configure_smtp(
    body: SmtpConfigurationUpdate,
    session: Session,
    user: IntegrationManager,
) -> SmtpConfigurationResponse:
    return await IntegrationService(session).configure_smtp(user.organization_id, body, user)


@router.post("/smtp/test-email", response_model=SmtpTestEmailResponse)
async def send_smtp_test_email(
    body: SmtpTestEmailRequest,
    session: Session,
    user: IntegrationTester,
) -> SmtpTestEmailResponse:
    return await IntegrationService(session).send_smtp_test_email(
        user.organization_id, str(body.recipient), user
    )


@router.get("/smtp/templates/{key}/preview", response_model=EmailTemplatePreviewResponse)
async def smtp_template_preview(
    key: TemplateKey,
    session: Session,
    user: IntegrationReader,
) -> EmailTemplatePreviewResponse:
    return await IntegrationService(session).email_template_preview(user.organization_id, key, user)


@router.put("/{key}", response_model=IntegrationResponse)
async def configure_integration(
    key: str,
    body: IntegrationConfigurationUpdate,
    session: Session,
    user: IntegrationManager,
) -> IntegrationResponse:
    return await IntegrationService(session).configure(user.organization_id, key, body.values, user)


@router.delete("/{key}", response_model=IntegrationOperationResponse)
async def disconnect_integration(
    key: str, session: Session, user: IntegrationManager
) -> IntegrationOperationResponse:
    await IntegrationService(session).disconnect(user.organization_id, key, user)
    return IntegrationOperationResponse(
        key=key, configured=False, message="Integration disconnected"
    )


@router.post("/{key}/test", response_model=IntegrationTestResponse)
async def test_integration(
    key: str, session: Session, user: IntegrationTester
) -> IntegrationTestResponse:
    return await IntegrationService(session).test_connection(user.organization_id, key, user)


@router.post("/{key}/synchronize", response_model=IntegrationOperationResponse)
async def synchronize_integration(
    key: str, session: Session, user: IntegrationManager
) -> IntegrationOperationResponse:
    await IntegrationService(session).synchronize(user.organization_id, key, user)
    return IntegrationOperationResponse(
        key=key,
        configured=True,
        message="Provider synchronization queued",
    )


@router.get("/{key}/audit", response_model=list[IntegrationAuditResponse])
async def integration_audit(
    key: str, session: Session, user: IntegrationReader
) -> list[IntegrationAuditResponse]:
    rows = await IntegrationService(session).audit_history(user.organization_id, key)
    return [
        IntegrationAuditResponse(
            action=row.action,
            status=str(row.audit_metadata.get("status", "recorded")),
            created_at=row.created_at,
            actor_id=str(row.user_id) if row.user_id else None,
            latency_ms=_audit_int(row.audit_metadata, "latency_ms"),
            diagnostic=(
                str(row.audit_metadata["diagnostic"])
                if isinstance(row.audit_metadata, dict) and row.audit_metadata.get("diagnostic")
                else None
            ),
            recipient=(
                str(row.audit_metadata["recipient"])
                if isinstance(row.audit_metadata, dict) and row.audit_metadata.get("recipient")
                else None
            ),
            revision=_audit_int(row.audit_metadata, "revision"),
            template_key=(
                str(row.audit_metadata["template_key"])
                if isinstance(row.audit_metadata, dict) and row.audit_metadata.get("template_key")
                else None
            ),
            template_version=(
                str(row.audit_metadata["template_version"])
                if isinstance(row.audit_metadata, dict)
                and row.audit_metadata.get("template_version")
                else None
            ),
        )
        for row in rows
    ]
