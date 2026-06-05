"""全量 API 路由鉴权分类审计。"""

from collections.abc import Iterable

from fastapi.routing import APIRoute

from app.api.deps import get_current_farm, get_current_user, require_admin
from app.main import app


PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("GET", "/api/app/version"),
    ("GET", "/weather/forecast"),
    ("GET", "/planting/operation-types"),
}

IGNORED_ROUTES: set[str] = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

PROTECTION_DEPENDENCIES = {
    get_current_user,
    get_current_farm,
    require_admin,
}


def test_all_http_routes_have_auth_classification():
    """每个业务 HTTP 路由都必须公开白名单或受鉴权依赖保护。"""
    unclassified: list[str] = []

    for route in _api_routes():
        for method in _route_methods(route):
            route_key = (method, route.path)
            if route.path in IGNORED_ROUTES or route_key in PUBLIC_ROUTES:
                continue
            if not _route_has_protection(route):
                unclassified.append(f"{method} {route.path}")

    assert unclassified == [], "发现未归类或未受保护的 API 路由：\n" + "\n".join(
        sorted(unclassified)
    )


def test_public_routes_are_explicit_and_limited():
    """公开白名单只能包含真实存在的路由。"""
    registered = {
        (method, route.path)
        for route in _api_routes()
        for method in _route_methods(route)
        if route.path not in IGNORED_ROUTES
    }

    missing = sorted(PUBLIC_ROUTES - registered)

    assert missing == []


def _api_routes() -> Iterable[APIRoute]:
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route


def _route_methods(route: APIRoute) -> set[str]:
    return {method for method in route.methods if method not in {"HEAD", "OPTIONS"}}


def _route_has_protection(route: APIRoute) -> bool:
    return any(call in PROTECTION_DEPENDENCIES for call in _dependency_calls(route))


def _dependency_calls(route: APIRoute) -> set[object]:
    calls: set[object] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        calls.add(dependency.call)
        stack.extend(dependency.dependencies)
    return calls
