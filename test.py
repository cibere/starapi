from starapi import Application, Request, Response, Server

app1 = Application(debug=True)
app2 = Application(debug=True)


@app1.route("/")
async def app1_index(request: Request) -> Response:
    return Response.ok("Hello from app 1")


@app1.route("/test")
async def app1_indexest(request: Request) -> Response:
    return Response.ok("Hello from app 1 test")


@app2.route("/")
async def app2_index(request: Request) -> Response:
    return Response.ok("Hello from app 2")


if __name__ == "__main__":
    server = Server()
    server.register_app(app1, prefix="v1")
    server.register_app(app2, prefix="v2")

    print(app1_index._path_data)

    server.run()
