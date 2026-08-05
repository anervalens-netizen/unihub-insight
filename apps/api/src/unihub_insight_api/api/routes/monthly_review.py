from typing import Annotated

from fastapi import APIRouter, Depends, Query

from unihub_insight_api.api.dependencies import RepositoryDependency, ScopeDependency
from unihub_insight_api.auth import require_capability
from unihub_insight_api.domain import Capability, MonthlyReviewResponse, UserContext

router = APIRouter(prefix="/api/v1", tags=["monthly-review"])


@router.get("/monthly-review", response_model=MonthlyReviewResponse)
async def monthly_review(
    repository: RepositoryDependency,
    scope: ScopeDependency,
    _user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
    recent_months: Annotated[int, Query(ge=3, le=12)] = 3,
) -> MonthlyReviewResponse:
    return await repository.get_monthly_review(scope, recent_months)
