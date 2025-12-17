# app/middleware/r2_public_url.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.services.r2_helper import to_presigned_url
import json

class R2PublicURLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if "application/json" not in response.headers.get("content-type", ""):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            data = json.loads(body)
        except:
            return response

        def transform(obj):
            if isinstance(obj, dict):
                if "cover_image" in obj and obj["cover_image"]:
                    obj["cover_image_url"] = to_presigned_url(obj["cover_image"])
                for v in obj.values():
                    transform(v)
            elif isinstance(obj, list):
                for i in obj:
                    transform(i)

        transform(data)

        return JSONResponse(content=data, status_code=response.status_code)
