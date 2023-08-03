import inspect
from typing import Type

import msgspec
from msgspec import _json_schema


def convert_to_msgspec(typ: Type) -> msgspec.inspect.Type:
    translator = msgspec.inspect._Translator([typ])
    t, args, _ = msgspec.inspect._origin_args_metadata(typ)
    return translator._translate_inner(t, args)


def convert_to_openapi(typ: msgspec.inspect.Type) -> dict:
    return _json_schema._to_schema(typ, {}, "#/$defs/{name}", False)


first = convert_to_msgspec(tuple[bool, str, int])
print(first)
second = convert_to_openapi(first)
print(second)

"""import asyncio

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
"""
