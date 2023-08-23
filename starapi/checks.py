from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from ._types import Check
    from .routing import Route, WebSocketRoute

T = TypeVar('T')

__all__ = ('check',)


def check(check_func: Check) -> Callable[[T], T]:
    def decorator(route_func: T) -> T:
        if isinstance(route_func, (Route, WebSocketRoute)):
            route_func._checks.append(check_func)  # type: ignore
        else:
            checks = getattr(route_func, "__starapi_checks__", [])
            checks.append(check_func)
            setattr(route_func, "__starapi_checks__", checks)
        return route_func

    return decorator
