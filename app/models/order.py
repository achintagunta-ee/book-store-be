# app/models/order.py
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship

from app.models.order_item import OrderItem

if TYPE_CHECKING:
    from .user import User
    from .address import Address


class Order(SQLModel, table=True):
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # ============ User/Guest Identification ============
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", nullable=True)
    address_id: Optional[int] = Field(default=None, foreign_key="address.id", nullable=True)
    
    # ============ Guest Information ============
    guest_email: Optional[str] = Field(default=None, max_length=255, nullable=True)
    guest_name: Optional[str] = Field(default=None, max_length=255, nullable=True)
    guest_phone: Optional[str] = Field(default=None, max_length=20, nullable=True)
    
    # ============ Guest Shipping Address ============
    guest_address_line1: Optional[str] = Field(default=None, max_length=500, nullable=True)
    guest_address_line2: Optional[str] = Field(default=None, max_length=500, nullable=True)
    guest_city: Optional[str] = Field(default=None, max_length=100, nullable=True)
    guest_state: Optional[str] = Field(default=None, max_length=100, nullable=True)
    guest_pincode: Optional[str] = Field(default=None, max_length=10, nullable=True)
    guest_country: Optional[str] = Field(default="India", max_length=100, nullable=True)
    
    # ============ Order Amounts ============
    subtotal: float = Field(default=0.0)
    shipping: float = Field(default=0.0)
    tax: Optional[float] = Field(default=0.0, nullable=True)
    total: float = Field(default=0.0)
    
    # ============ Order Status ============
    status: str = Field(default="pending")
    payment_mode: str = Field(default="online")
    placed_by: str = Field(default="user")
    
    # ============ Timestamps ============
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # ============ Tracking Information ============
    tracking_id: Optional[str] = Field(default=None, nullable=True)
    tracking_url: Optional[str] = Field(default=None, nullable=True)
    shipped_at: Optional[datetime] = Field(default=None, nullable=True)
    delivered_at: Optional[datetime] = Field(default=None, nullable=True)
    
    # ============ Relationships ============
    user: Optional["User"] = Relationship(back_populates="orders")
    address: Optional["Address"] = Relationship(back_populates="orders")
    items: list["OrderItem"] = Relationship(back_populates="order")
    
    # ============ Helper Properties ============
    @property
    def is_guest_order(self) -> bool:
        """Check if this is a guest order"""
        return self.user_id is None and self.guest_email is not None
    
    @property
    def customer_email(self) -> Optional[str]:
        """Get customer email (works for both guest and registered users)"""
        if self.is_guest_order:
            return self.guest_email
        return self.user.email if self.user else None
    
    @property
    def customer_name(self) -> Optional[str]:
        """Get customer name (works for both guest and registered users)"""
        if self.is_guest_order:
            return self.guest_name
        return self.user.name if self.user else None


class OrderStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    EXPIRED = "expired"

class CancellationStatus:
    PENDING = "pending"
    REFUNDED = "refunded"
    REJECTED = "rejected"


    user: Optional["User"] = Relationship(back_populates="orders")