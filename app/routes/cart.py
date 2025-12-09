from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models.cart import CartItem
from app.models.book import Book
from app.models.user import User
from app.schemas.cart_schemas import CartAddRequest, CartUpdateRequest
from app.utils.token import get_current_user  # JWT dependency

router = APIRouter()

# Add to Cart 

@router.post("/add")
def add_to_cart(
    data: CartAddRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Ensure book exists
    book = session.get(Book, data.book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    existing = session.exec(
        select(CartItem).where(
            CartItem.book_id == data.book_id,
            CartItem.user_id == current_user.id
        )
    ).first()

    if existing:
        existing.quantity += data.quantity
        session.add(existing)
        session.commit()
        return {
                 "message": "Quantity updated",
         "item": {
        "id": existing.id,
        "book_id": existing.book_id,
        "user_id": existing.user_id,
        "quantity": existing.quantity,
        "created_at": existing.created_at
    }
}

    item = CartItem(
        user_id=current_user.id,
        book_id=data.book_id,
        quantity=data.quantity
    )

    session.add(item)
    session.commit()
    session.refresh(item)

    return {"message": "Added to cart", "item": item}

# View Cart 

@router.get("/")
def get_cart(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    cart_items = session.exec(
        select(CartItem, Book)
        .join(Book, CartItem.book_id == Book.id)
        .where(CartItem.user_id == current_user.id)
    ).all()

    items_response = []
    subtotal = 0

    for cart_item, book in cart_items:
        # Determine best price
        effective_price = (
            book.offer_price 
            if book.offer_price 
            else book.discount_price 
            if book.discount_price 
            else book.price
        )

        subtotal += effective_price * cart_item.quantity

        items_response.append({
            "item_id": cart_item.id,
            "book_id": book.id,
            "book_name": book.title,
            "slug": book.slug,
            "cover_image": book.cover_image,
            "price": book.price,
            "discount_price": book.discount_price,
            "offer_price": book.offer_price,
            "effective_price": effective_price,
            "quantity": cart_item.quantity,
            "stock": book.stock,
            "in_stock": book.in_stock,
            "total": effective_price * cart_item.quantity
        })

    # SHIPPING RULE
    shipping = 0 if subtotal >= 500 else 150



    final_total = subtotal  + shipping

    return {
        "items": items_response,
        "summary": {
            "subtotal": subtotal,
            "shipping": shipping,
            "final_total": final_total
        }
    }

# Update Cart 
@router.put("/update/{item_id}")
def update_cart_item(
    item_id: int,
    data: CartUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = session.get(CartItem, item_id)

    if not item or item.user_id != current_user.id:
        raise HTTPException(404, "Cart item not found")

    if data.quantity <= 0:
        session.delete(item)
        session.commit()
        return {"message": "Item removed"}

    item.quantity = data.quantity
    session.add(item)
    session.commit()
    session.refresh(item)

    return {"message": "Quantity updated", "item": item}

# Remove Cart 

@router.delete("/remove/{item_id}")
def remove_item(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    item = session.get(CartItem, item_id)

    if not item or item.user_id != current_user.id:
        raise HTTPException(404, "Item not found")

    session.delete(item)
    session.commit()

    return {"message": "Item removed from cart"}

# Clear Cart 

@router.delete("/clear")
def clear_cart(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    for item in items:
        session.delete(item)

    session.commit()

    return {"message": "Cart cleared"}
