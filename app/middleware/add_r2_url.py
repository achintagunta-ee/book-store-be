# app/middleware/add_r2_url.py

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import os
import json

R2_PUBLIC_BASE = os.getenv("CLOUDFLARE_R2_PUBLIC_BASE")

def attach_url(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "cover_image" and v and not v.startswith("http"):
                obj[k] = f"{R2_PUBLIC_BASE}/{v}"
            else:
                attach_url(v)
    elif isinstance(obj, list):
        for i in obj:
            attach_url(i)

class AddR2URLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if not isinstance(response, JSONResponse):
            return response

        data = json.loads(response.body)
        attach_url(data)

        return JSONResponse(content=data, status_code=response.status_code)
