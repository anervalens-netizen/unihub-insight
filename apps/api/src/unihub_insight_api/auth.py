from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status

from unihub_insight_api.config import Settings
from unihub_insight_api.domain import Capability, UserContext

ALL_CAPABILITIES = frozenset(Capability)


def _groups(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    normalized = value.replace(";", ",")
    return tuple(dict.fromkeys(item.strip() for item in normalized.split(",") if item.strip()))


def _capabilities(settings: Settings, groups: tuple[str, ...]) -> frozenset[Capability]:
    group_set = set(groups)
    capabilities: set[Capability] = set()
    if group_set & settings.parse_groups(settings.analytics_groups):
        capabilities.add(Capability.ANALYTICS)
    if group_set & settings.parse_groups(settings.management_groups):
        capabilities.update({Capability.ANALYTICS, Capability.MANAGEMENT})
    if group_set & settings.parse_groups(settings.hr_groups):
        capabilities.update({Capability.ANALYTICS, Capability.MANAGEMENT, Capability.HR})
    if group_set & settings.parse_groups(settings.pnl_groups):
        capabilities.update({Capability.ANALYTICS, Capability.MANAGEMENT, Capability.PNL})
    if group_set & settings.parse_groups(settings.admin_groups):
        capabilities.update(ALL_CAPABILITIES)
    return frozenset(capabilities)


async def get_current_user(request: Request) -> UserContext:
    settings = cast(Settings, request.app.state.settings)
    if settings.auth_mode == "demo":
        return UserContext(
            subject="demo-admin",
            email="demo@unihub.local",
            name="Demo Administrator",
            groups=("demo",),
            capabilities=ALL_CAPABILITIES,
            is_demo=True,
        )

    supplied_secret = request.headers.get("x-unihub-proxy-secret", "")
    expected_secret = settings.trusted_proxy_secret or ""
    if not supplied_secret or not secrets.compare_digest(supplied_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trusted identity boundary is missing or invalid.",
        )

    subject = request.headers.get("x-authentik-uid", "").strip()
    email = request.headers.get("x-authentik-email", "").strip() or None
    name = request.headers.get("x-authentik-name", "").strip() or None
    groups = _groups(request.headers.get("x-authentik-groups"))
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Verified subject is missing.",
        )
    return UserContext(
        subject=subject,
        email=email,
        name=name,
        groups=groups,
        capabilities=_capabilities(settings, groups),
    )


def require_capability(capability: Capability) -> Callable[..., UserContext]:
    async def dependency(
        user: Annotated[UserContext, Depends(get_current_user)],
    ) -> UserContext:
        if capability not in user.capabilities:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Capability {capability.value} is required.",
            )
        return user

    return dependency
