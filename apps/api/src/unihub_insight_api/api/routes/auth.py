from fastapi import APIRouter

from unihub_insight_api.api.dependencies import UserDependency
from unihub_insight_api.domain import UserContext

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/me", response_model=UserContext)
async def me(user: UserDependency) -> UserContext:
    return user
