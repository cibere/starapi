import http

__all__ = (
    "StarApiException",
    "GroupException",
    "GroupAlreadyAdded",
    "StartupException",
    "UvicornNotInstalled",
    "ClientException",
    "ClientDisconnect",
)


class StarApiException(Exception):
    ...


class ClientException(StarApiException):
    ...


class ClientDisconnect(ClientException):
    ...


class GroupException(StarApiException):
    ...


class GroupAlreadyAdded(GroupException):
    name: str

    def __init__(self, name: str) -> None:
        super().__init__(f"The '{name}' group was already added")
        self.name = name


class StartupException(StarApiException):
    ...


class UvicornNotInstalled(StartupException):
    def __init__(self) -> None:
        super().__init__(f"Uvicorn is not installed.")


class HTTPException(StarApiException):
    def __init__(
        self,
        status_code: int,
        detail: str | None = None,
        headers: dict | None = None,
    ) -> None:
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase
        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __str__(self) -> str:
        return f"{self.status_code}: {self.detail}"

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"
