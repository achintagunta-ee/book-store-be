from fastapi import FastAPI
from app.database import create_db_and_tables
from app.routes import auth ,users , books

app = FastAPI(title="Hithabodha Bookstore API")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"]) 
app.include_router(books.router, prefix="/books", tags =["Books"])

app.get("/")
def root():
    return {
        "auth_endpoints": ["/auth/register", "/auth/login" ,"auth/google"],
        "user_endpoints": ["/users/me", "/users/admin-feature"] ,
        "book_endpoints":["/books","/books/{id}"]
    }


