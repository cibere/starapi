import asyncio

import aiohttp


async def test2():
    async with aiohttp.ClientSession() as cs:
        ws = await cs.ws_connect("ws://127.0.0.1:8000/test2")
        print("Connected to test2")
        await ws.send_json({"msg": "Hello"})
        for i in range(20):
            msg = f"Hola x{i + 1}"
            await ws.send_str(msg)
            print(f"Sent {msg}")


async def test1():
    async with aiohttp.ClientSession() as cs:
        ws = await cs.ws_connect("ws://127.0.0.1:8000/test1")
        print("Connected to test1")
        await ws.send_json({"msg": "Hello"})
        print("Sent")
        print("-" * 50)
        async for msg in ws:
            print(msg.data)


asyncio.run(test2())
