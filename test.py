from starapi import Application, Parameter, Request, Response
from starapi.requests import WebSocket
from starapi.routing import WebSocketRoute


class Lifespan:
    def __init__(self, app: Application) -> None:
        ...

    async def __aenter__(self) -> None:
        print("Entering")

    async def __aexit__(self, *exc_info: object) -> None:
        print("Exiting")


app = Application(debug=True, lf=Lifespan)


@app.route("/save", hidden=True)
async def save(request: Request) -> Response:
    data = request.app._state.construct_openapi_file(
        title="My API Docs", version="0.0.1"
    )
    print(data)
    with open("new_openapi.json", "w", encoding="utf-8") as f:
        import json

        json.dump(data, f)
    return Response("Hello")


@app.route("/", query_parameters=[Parameter(required=False, name="name", type=str)])
async def index(request: Request) -> Response:
    return Response("Hello")


@app.route(
    "/{id:float}", path_parameters=[Parameter(required=True, name="id", type=float)]
)
async def index2(request: Request) -> Response:
    return Response(f"Hello {request.path_params['id']} f")


app.run()
