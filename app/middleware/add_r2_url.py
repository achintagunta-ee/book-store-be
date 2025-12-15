# app/middleware/add_r2_url.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.services.r2_helper import public_url


class AddR2URLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Only modify JSON responses
        if isinstance(response, JSONResponse):
            body = response.body.decode()
            try:
                import json
                data = json.loads(body)

                def convert(obj):
                    if isinstance(obj, dict):
                        return {
                            k: (public_url(v) if k == "cover_image" and isinstance(v, str) else convert(v))
                            for k, v in obj.items()
                        }
                    if isinstance(obj, list):
                        return [convert(i) for i in obj]
                    return obj

                new_data = convert(data)
                return JSONResponse(content=new_data, status_code=response.status_code)

            except Exception:
                return response

        return response
