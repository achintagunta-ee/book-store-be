from pydantic import BaseModel

class GoogleTokenRequest(BaseModel):
    token: str

class GoogleUserInfo(BaseModel):
    email: str
    name: str
    picture: str | None = None