"""Global search API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from meetinghq_api.infrastructure.database import get_database_session
from meetinghq_api.modules.auth.presentation.dependencies import CurrentUser
from meetinghq_api.modules.search.schemas import SearchResponse
from meetinghq_api.modules.search.service import GlobalSearchService

router = APIRouter(prefix="/search", tags=["search"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


@router.get("", response_model=SearchResponse)
async def global_search(
    user: CurrentUser,
    session: Session,
    q: Annotated[str, Query(min_length=2, max_length=160)],
    limit: Annotated[int, Query(ge=1, le=50)] = 24,
) -> SearchResponse:
    return await GlobalSearchService(session).search(user, q, limit)
