from pydantic import BaseModel

class AddressCreate(BaseModel):
    first_name: str
    last_name: str
    address: str
    city: str
    state: str
    zip_code: str
