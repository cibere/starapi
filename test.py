from starapi import Application, Request, Response

app = Application(debug=True)


@app.route("/")
async def index(request: Request) -> Response:
    data = await request.body()

    # print("Starting")
    async for chunk in request.stream():
        print(f"{chunk=}")
    # print("Starting")
    async for chunk in request.stream():
        print(f"{chunk=}")

    return Response("d")


app.run()
