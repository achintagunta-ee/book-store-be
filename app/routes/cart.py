from fastapi import APIRouter, Depends, HTTPException 
from sqlmodel import Session, select
from app.database import get_session
from app.models import book
from app.models.cart import CartItem
from app.models.book import Book
from app.models.user import User
from app.schemas.cart_schemas import CartAddRequest, CartUpdateRequest
from app.services.r2_helper import to_presigned_url
from app.utils.token import get_current_user  # JWT dependency
from app.models.cart import CartItem 
from datetime import datetime


router = APIRouter()

# Add to Cart 

@router.post("/add")
def add_to_cart(
    data: CartAddRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    added_items = []

    for item in data.items:
        book = session.get(Book, item.book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book not found: {item.book_id}"
            )

        final_price = book.offer_price or book.discount_price or book.price

        existing_item = session.exec(
            select(CartItem).where(
                CartItem.user_id == current_user.id,
                CartItem.book_id == item.book_id
            )
        ).first()

        if existing_item:
            existing_item.quantity += item.quantity
            session.add(existing_item)
            added_items.append(existing_item)
        else:
            new_item = CartItem(
                user_id=current_user.id,
                book_id=book.id,
                quantity=item.quantity,
                book_title=book.title,
                price=final_price,
                created_at=datetime.utcnow()
            )
            session.add(new_item)
            added_items.append(new_item)

    session.commit()
    return {
        "message": "Books added to cart",
    }



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
            "cover_image":book.cover_image,
            "cover_image_url": to_presigned_url(book.cover_image)if book.cover_image else None,
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
            "cover_image":book.cover_image,
            "cover_image_url": to_presigned_url(book.cover_image)if book.cover_image else None,
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
def clear_cart(session: Session, user_id: int):
    items = session.exec(
        select(CartItem).where(CartItem.user_id == user_id)
    ).all()

    for item in items:
        session.delete(item)

    session.commit()


@router.delete("/clear")
def clear_cart_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    clear_cart(session, current_user.id)
    return {"message": "Cart cleared"}



@router.get("/details", response_model=None)
def get_my_cart(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    items = session.exec(
    select(CartItem, Book)
    .join(Book, CartItem.book_id == Book.id)
    .where(CartItem.user_id == current_user.id)
).all()


    if not items:
        return {
            "items": [],
            "subtotal": 0,
            "shipping": 0,
            "total": 0
        }

    item_list = []
    subtotal = 0

    for item ,book in items:
        line_total = item.price * item.quantity
        subtotal += line_total

        item_list.append({
            "book_id": item.book_id,
            "book_title": item.book_title,
            "price": item.price,
            "cover_image":book.cover_image,
            "cover_image_url": to_presigned_url(book.cover_image)if book.cover_image else None,
            "quantity": item.quantity,
            "total": line_total
        })

    # Example logic
    shipping = 0 if subtotal > 500 else 150
    total = subtotal + shipping

    return {
        "items": item_list,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total
    }

