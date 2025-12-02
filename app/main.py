from fastapi import FastAPI
from app.database import create_db_and_tables
from app.routes import auth, books_admin, categories_admin ,users , categories_public ,users , books_public

from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routes import books_public

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    create_db_and_tables()
    yield
    # Shutdown: Add cleanup logic here if needed

app = FastAPI(title="Hithabodha Bookstore API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"]) 
app.include_router(books_admin.router, prefix="/admin/books", tags =["Admin Books"])
app.include_router(categories_admin.router,prefix="/admin/categories", tags=["Admin Categories"])
app.include_router(books_public.router, prefix="/books", tags=["Public Books"])
app.include_router(categories_public.router, prefix="/categories", tags=["Public Categories"])


app.get("/")
def root():
    return {
        "auth_endpoints": ["/auth/register", "/auth/login" ,"auth/google"],
        "user_endpoints": ["/users/me", "/users/admin-feature"] ,
        "book_endpoints":["/books","/books/{id}"],
        "category_endpoints":["/categories","/categories/{id}"]
    }
