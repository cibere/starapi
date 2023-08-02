from starapi import Application, Request, Response
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


@app.route("/")
async def index(request: Request) -> Response:
    return Response("Hello")


@app.route("/{id:float}")
async def index2(request: Request) -> Response:
    return Response(f"Hello {request.path_params['id']} f")


@app.route("/{id:float2}")
async def index2(request: Request) -> Response:
    return Response(f"Hello {request.path_params['id']} f2")


@app.route("/{id:epoch-timestamp}")
async def index2(request: Request) -> Response:
    return Response(f"You gave me {request.path_params['id'].isoformat()}.")


@app.route("/iso/{id:iso-timestamp}")
async def index2(request: Request) -> Response:
    return Response(f"You gave me {request.path_params['id'].timestamp()}.")


app.run()
