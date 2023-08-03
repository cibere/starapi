from typing import Literal

import msgspec

from starapi import Application, Parameter, Request, Response

app = Application(debug=True)


class ExamplePayload(msgspec.Struct):
    youtube_url: str
    delay: int
    tags: list[str]


class ResponsePayload(msgspec.Struct):
    status: bool
    message: Literal["Successfully updated your profile"]


@app.route(
    "/{id:int}",
    path_parameters=[Parameter(required=True, name="id", type=int)],
    methods=["POST"],
    payload=ExamplePayload,
    responses={200: ResponsePayload},
)
async def index2(request: Request) -> Response:
    return Response(f"Hello {request.path_params['id']}")


app.run()
