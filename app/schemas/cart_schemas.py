from sqlmodel import SQLModel

class CartAddRequest(SQLModel):
    book_id: int
    quantity: int = 1

class CartUpdateRequest(SQLModel):
    quantity: int
