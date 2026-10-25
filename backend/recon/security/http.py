from typing import Any

from fastapi import HTTPException


class BodyBudgetMiddleware:
    """Count streamed bytes before multipart parsing, even without Content-Length."""

    def __init__(self, app: Any, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Any:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(
                        413,
                        detail={
                            "code": "FILE_TOO_LARGE",
                            "message": "Request exceeds the upload budget, including streamed data.",
                        },
                    )
            return message

        await self.app(scope, limited_receive, send)
