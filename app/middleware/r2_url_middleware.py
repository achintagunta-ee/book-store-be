from starlette.middleware.base import BaseHTTPMiddleware
from app.routes.storage import generate_presigned_url


class R2URLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if hasattr(response, "body_iterator"):
            return response

        if "application/json" in response.headers.get("content-type", ""):
            content = response.json()

            def fix(obj):
                if isinstance(obj, dict):
                    if "cover_image" in obj and obj["cover_image"]:
                        obj["cover_image_url"] = generate_presigned_url(obj["cover_image"])
                    for v in obj.values():
                        fix(v)
                elif isinstance(obj, list):
                    for item in obj:
                        fix(item)

            fix(content)
            response.media = content

        return response
