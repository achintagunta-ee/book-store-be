from fastapi import FastAPI
from app.database import create_db_and_tables
from app.routes import auth, books_admin, categories_admin, users, categories_public, books_public, book_detail, review, cart
import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(title="Hithabodha Bookstore API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "https://hbn-be.efficientemengineering.com",
        "https://book.efficientemengineering.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"]) 
app.include_router(books_admin.router, prefix="/admin/books", tags=["Admin Books"])
app.include_router(categories_admin.router, prefix="/admin/categories", tags=["Admin Categories"])
app.include_router(books_public.router, prefix="/books", tags=["Public Books"])
app.include_router(categories_public.router, prefix="/categories", tags=["Public Categories"])
app.include_router(book_detail.router, prefix="/book", tags=["Book Details"])
app.include_router(review.router, prefix="/reviews", tags=["Reviews"])
app.include_router(cart.router, prefix="/cart", tags=["Cart"])

# Use system temp directory instead of local uploads folder
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "hithabodha_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    return {
        "auth_endpoints": ["/auth/register", "/auth/login", "/auth/google"],
        "user_endpoints": ["/users/me", "/users/admin-feature"],
        "book_endpoints": ["/books", "/books/{id}"],
        "category_endpoints": ["/categories", "/categories/{id}"]
    }