from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.services.r2_helper import public_url
import json

class R2PublicURLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Only modify JSON responses
        if "application/json" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            data = json.loads(body)
        except:
            return response  # Not JSON → return unchanged

        # Recursively replace R2 keys with URLs
        def transform(obj):
            if isinstance(obj, dict):
                if "cover_image" in obj and obj["cover_image"]:
                    obj["cover_image_url"] = public_url(obj["cover_image"])
                for value in obj.values():
                    transform(value)

            elif isinstance(obj, list):
                for item in obj:
                    transform(item)

        transform(data)

        return JSONResponse(content=data, status_code=response.status_code)
