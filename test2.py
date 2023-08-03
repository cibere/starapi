from typing import Callable, Optional, ParamSpec, TypeVar

import uvicorn

T = TypeVar("T")
P = ParamSpec("P")
from starapi.server import BaseASGIApp


def take_annotation_from(
    this: Callable[P, Optional[T]]
) -> Callable[[Callable], Callable[P, Optional[T]]]:
    def decorator(real_function: Callable) -> Callable[P, Optional[T]]:
        def new_function(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
            return real_function(*args, **kwargs)

        return new_function

    return decorator


class SomeApp(BaseASGIApp):
    @take_annotation_from(uvicorn.run)
    def run(self, *args, **kwargs) -> None:
        try:
            import uvicorn
        except ImportError:
            raise RuntimeError(
                "'uvicorn' must be installed to use the default 'run' method"
            ) from None
        else:
            uvicorn.run(*args, **kwargs)


SomeApp().run(host="127.0.0.1")
