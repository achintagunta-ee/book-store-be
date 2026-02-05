from sqlmodel import SQLModel, Field ,Relationship
from typing import Optional, TYPE_CHECKING , List
from datetime import datetime
from app.models.review import Review


if TYPE_CHECKING:
    from .category import Category
if TYPE_CHECKING:
    from app.models.book_image import BookImage

class Book(SQLModel, table=True):
    # main info
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    slug: str
    excerpt: Optional[str] = None
    description: str

    # Author and meta
    author: str
    language: Optional[str] = None
    rating: Optional[float] = 0.0

    # Image
    cover_image: Optional[str] = None

    # Physical book
    price: float
    discount_price: Optional[float] = None
    offer_price: Optional[float] = None
    stock: Optional[int] = None

    # 📘 eBook fields (NEW)
    is_ebook: bool = Field(default=False)
    ebook_price: Optional[float] = None
    pdf_key: Optional[str] = Field(
        default=None,
        description="R2/S3 object key for ebook PDF"
    )

    # Metadata
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    is_featured: bool = False
    is_featured_author: bool = False

    # timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # category
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    category: Optional["Category"] = Relationship(back_populates="books")

    # tags
    tags: Optional[str] = None

    # relationships
    reviews: List["Review"] = Relationship(back_populates="book")
    images: list["BookImage"] = Relationship(back_populates="book")

    @property
    def in_stock(self) -> bool:
        return self.stock is not None and self.stock > 0
