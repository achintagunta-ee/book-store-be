from fastapi import FastAPI
from app.database import create_db_and_tables
from app.config import settings
#from app.middleware.r2_public_url import R2PublicURLMiddleware
from app.middleware.r2_public_url import R2PublicURLMiddleware
from app.routes import (
    admin,
    auth,
    books_public,
    payments,
    users,
    books_admin,
    categories_admin,
    categories_public,
    book_detail,
    review,
    cart,
    checkout,
    wishlist,
    storage,
    payments
)

import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run DB creation ONLY in local
    if settings.ENV == "local":
        create_db_and_tables()
    yield

app = FastAPI(title="Hithabodha Bookstore API", lifespan=lifespan)
app.add_middleware(R2PublicURLMiddleware)

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
app.include_router(checkout.router , prefix="/checkout", tags=["Checkout"])
app.include_router(wishlist.router, prefix="/wishlist" , tags=["Wishlist"])
app.include_router(storage.router, prefix="/storage",tags=["Files Storage"])
app.include_router(admin.router,prefix="/admin",tags= ["Admin Endpoints"])
app.include_router(payments.router,prefix="/admin/payments", tags=["Admin Payments"])

# Use system temp directory instead of local uploads folder
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "hithabodha_uploads")
BOOK_COVER_DIR = os.path.join(UPLOAD_DIR, "book_covers")
os.makedirs(BOOK_COVER_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    return {
        "auth_endpoints": [
            "/auth/register", "/auth/login", "/auth/google",
            "/auth/forgot-password", "/auth/reset-password", "/auth/logout"
        ],
        "user_endpoints": [
            "/users/me", "/users/update-profile"
        ],
        "admin_book_endpoints": [
            "/admin/books/", "/admin/books/{book_id}", 
            "/admin/books/filter", "/admin/books/list"
        ],
        "admin_category_endpoints": [
            "/admin/categories/", "/admin/categories/{category_id}"
        ],
        "public_books": [
            "/books", "/books/{book_id}"
        ],
        "public_categories": [
            "/categories", "/categories/{category_id}"
        ],
        "reviews": [
            "/reviews", "/reviews/{review_id}", "/reviews/book/{book_id}"
        ],
        "cart": [
            "/cart", "/cart/add", "/cart/update/{id}",
            "/cart/remove/{id}", "/cart/clear"
        ]
    }

