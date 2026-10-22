from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


MAX_AUTH_REQUEST_BYTES = 16 * 1024
MAX_API_REQUEST_BYTES = 1024 * 1024


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        maximum = (
            MAX_AUTH_REQUEST_BYTES
            if path.startswith("/api/auth/")
            else MAX_API_REQUEST_BYTES
        )
        content_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if content_lengths:
            if any(not value.isdigit() for value in content_lengths):
                await JSONResponse(
                    {"detail": "Invalid Content-Length header."},
                    status_code=400,
                )(scope, receive, send)
                return
            try:
                parsed_lengths = [int(value) for value in content_lengths]
            except ValueError:
                await JSONResponse(
                    {"detail": "Invalid Content-Length header."},
                    status_code=400,
                )(scope, receive, send)
                return
            if any(length < 0 for length in parsed_lengths) or len(set(parsed_lengths)) != 1:
                await JSONResponse(
                    {"detail": "Invalid Content-Length header."},
                    status_code=400,
                )(scope, receive, send)
                return
            if parsed_lengths[0] > maximum:
                await self._too_large(scope, receive, send)
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > maximum:
                await self._too_large(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_body():
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {
                "type": "http.request",
                "body": bytes(body),
                "more_body": False,
            }

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _too_large(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        await JSONResponse(
            {"detail": "Request body too large."},
            status_code=413,
        )(scope, receive, send)
