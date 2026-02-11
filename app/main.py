from fastapi import FastAPI
from app.config import settings
from app.middleware.r2_public_url import R2PublicURLMiddleware
import app.models
from apscheduler.schedulers.background import BackgroundScheduler
from app.routes import (
    admin,
    admin_cancellation,
    admin_notifications,
    admin_orders,
    admin_payments,
    admin_settings,
    auth,
    books_public,
    checkout_guest,
    checkout_user,
    ebooks,
    ebooks_admin,
    health,
    order_cancellation,
    public_settings,
    user_library,
    user_orders,
    users,
    books_admin,
    categories_admin,
    categories_public,
    book_detail,
    review,
    cart,
    wishlist,
    storage,
    book_inventory,
    admin_analytics
)

import os
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

from app.services.order_expiry_service import expire_unpaid_ebooks, expire_unpaid_orders
from app.services.payment_remainders import send_ebook_payment_reminders, send_payment_reminders



@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        expire_unpaid_orders,
        trigger="interval",
        hours=1,
        id="expire_unpaid_orders",
        replace_existing=True,
    )

    scheduler.add_job(
        expire_unpaid_ebooks,
        trigger="interval",
        hours=1,
        id="expire_unpaid_ebooks",
        replace_existing=True,
    )

    # Send physical order payment reminders
    scheduler.add_job(
        send_payment_reminders,
        trigger="interval",
        hours=1,
        id="send_payment_reminders",
        replace_existing=True,
    )

    # Send ebook payment reminders
    scheduler.add_job(
        send_ebook_payment_reminders,
        trigger="interval",
        hours=1,
        id="send_ebook_payment_reminders",
        replace_existing=True,
    )
    scheduler.start()

    try:
        yield
    finally:
        scheduler.shutdown()

app = FastAPI(
    title="Hithabodha Bookstore API",
    lifespan=lifespan,
    servers=[
        {
            "url": "https://hbn-be.efficientemengineering.com",
            "description": "Production server",
        }
    ],
)
# Rate limiting setup
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from app.core.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(R2PublicURLMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
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
app.include_router(checkout_user.router , prefix="/checkout", tags=["Checkout User"])
app.include_router(checkout_guest.router , prefix="/checkout/guest", tags=["Checkout Guest"])
app.include_router(user_orders.router , prefix="/checkout/orders", tags=["User Orders"])
app.include_router(wishlist.router, prefix="/wishlist" , tags=["Wishlist"])
app.include_router(storage.router, prefix="/storage",tags=["Files Storage"])
app.include_router(admin.router,prefix="/admin",tags= ["Admin Endpoints"])
app.include_router(admin_payments.router,prefix="/admin/payments",tags= ["Admin Payments"])
app.include_router(admin_orders.router,prefix="/admin/orders",tags= ["Admin Orders"])
app.include_router(admin_notifications.router,prefix="/admin/notifications",tags= ["Admin Notifications"])
app.include_router(book_inventory.router,prefix="/admin/book",tags= ["Book Inventory"])
app.include_router(admin_settings.router,prefix="/admin/settings",tags= ["Admin Settings"])
app.include_router(public_settings.router,prefix="/settings",tags= ["Public Settings"])
app.include_router(order_cancellation.router,prefix="/orders/cancellations",tags= ["User Order Cancellation"])
app.include_router(admin_cancellation.router,prefix="/admin/cancellations",tags= ["Admin Order Cancellation"])
app.include_router(ebooks.router,prefix="/ebooks",tags= ["Ebook Purchase"])
app.include_router(user_library.router,prefix="/users/library",tags= ["Users Library"])
app.include_router(ebooks_admin.router,prefix="/ebooks/admin",tags=["Ebook Admin"]),
app.include_router(admin_analytics.router,prefix="/admin/analytics", tags=["Admin Analytics"])
app.include_router(health.router,prefix="/health",tags=["Health"])


# Use system temp directory instead of local uploads folder
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "hithabodha_uploads")
BOOK_COVER_DIR = os.path.join(UPLOAD_DIR, "book_covers")
os.makedirs(BOOK_COVER_DIR, exist_ok=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static"
)
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

