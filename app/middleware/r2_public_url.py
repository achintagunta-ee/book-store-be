# app/middleware/r2_public_url.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.services.r2_helper import to_presigned_url
import json

class R2PublicURLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

          #  Skip Swagger & OpenAPI
        if request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            return response

        # Only process JSON responses
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
                if "cover_image" in obj and isinstance(obj["cover_image"], str):
                    obj["cover_image_url"] = to_presigned_url(obj["cover_image"])

                if "profile_image" in obj and isinstance(obj["profile_image"], str):
                    obj["profile_image_url"] = to_presigned_url(obj["profile_image"])

                for v in obj.values():
                    transform(v)
            elif isinstance(obj, list):
                for i in obj:
                    transform(i)

        transform(data)

        return JSONResponse(content=data, status_code=response.status_code)
