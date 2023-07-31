from starapi import Application, Request, Response

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


@app.route("/{id:int}")
async def index2(request: Request) -> Response:
    return Response(f"Hello {request.path_params['id']}")


app.run()

