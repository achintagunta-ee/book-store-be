from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select 
from app.database import get_session
from app.models.user import User 
from app.models.order import Order 
from app.models.order_item import OrderItem
from app.models.address import Address
from app.utils.token import get_current_user
from app.schemas.address_schemas import AddressCreate
from app.routes.cart import clear_cart
from app.models.summary import CheckoutSummaryResponse , SummaryItem
from app.models.cart import CartItem
from app.models.book import Book
from app.schemas.orders_schemas import PlacedOrderItem , PlaceOrderResponse
from datetime import datetime, timedelta
import os
from reportlab.pdfgen import canvas
from fastapi.responses import FileResponse

router = APIRouter()

@router.post("/address")
def save_address(
    data: AddressCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    address = Address(user_id=current_user.id, **data.dict())

    session.add(address)
    session.commit()
    session.refresh(address)

    return {"message": "Address saved", "address_id": address.id}

@router.post("/summary", response_model=CheckoutSummaryResponse)
def checkout_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):

    # 1️⃣ Get user's address  
    address = session.exec(
        select(Address).where(Address.user_id == current_user.id)
    ).first()

    if not address:
        raise HTTPException(400, "No address found. Please add one.")

    # 2️⃣ Get cart details  
    cart_items = session.exec(
        select(CartItem).where(CartItem.user_id == current_user.id)
    ).all()

    if not cart_items:
        raise HTTPException(400, "Your cart is empty.")

    item_list = []
    subtotal = 0

    # 3️⃣ Build item list + subtotal  
    for item in cart_items:
        book = session.get(Book, item.book_id)
        if not book:
            continue

        total_price = item.quantity * book.price
        subtotal += total_price

        item_list.append({
            "book_title": book.title,
            "price": book.price,
            "quantity": item.quantity,
            "total": total_price
        })

    # 4️⃣ Shipping Logic  
    shipping = 0 if subtotal >= 500 else 150

    # 5️⃣ Tax (Optional example: 5%)  
    tax = subtotal * 0.05

    # 6️⃣ Final total  
    total = subtotal + shipping + tax

    # 7️⃣ Return summary  
    return CheckoutSummaryResponse(
    address_id=address.id,
    subtotal=subtotal,
    shipping=shipping,
    tax=tax,
    total=total,
    items=[
      SummaryItem(
            book_title=i["book_title"],
            price=i["price"],
            quantity=i["quantity"],
            total=i["total"]
        )
        for i in item_list
    ]
)

# Checkout button in Cart page

@router.post("/place-order", response_model=PlaceOrderResponse)
def place_order(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # --------------------------
    # 1️⃣ Fetch address
    # --------------------------
    address = session.get(Address, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    # --------------------------
    # 2️⃣ Fetch user's cart
    # --------------------------
    from app.routes.cart import get_cart_details
    cart = get_cart_details(session, current_user.id)

    if not cart or len(cart["items"]) == 0:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # --------------------------
    # 3️⃣ Create the order
    # --------------------------
    order = Order(
        user_id=current_user.id,
        address_id=address_id,
        subtotal=cart["subtotal"],
        shipping=cart["shipping"],
        tax=cart["tax"],
        total=cart["total"],
        status="pending"
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    # --------------------------
    # 4️⃣ Create order items
    # --------------------------
    placed_items = []

    for item in cart["items"]:
        order_item = OrderItem(
            order_id=order.id,
            book_id=item["book_id"],        # ✅ DICT KEY
            book_title=item["book_title"],  # ✅ DICT KEY
            price=item["price"],            # ✅ DICT KEY
            quantity=item["quantity"] 
        )
        session.add(order_item)
        placed_items.append(
           PlacedOrderItem(
              book_id=item["book_id"],
              quantity=item["quantity"],
              price=item["price"],
              book_title=item["book_title"],
              line_total=item["quantity"] * item["price"]
)

        )

    session.commit()

    # --------------------------
    # 5️⃣ Clear user cart
    # --------------------------
    clear_cart(session, current_user.id)

    # --------------------------
    # 6️⃣ Calculate estimated delivery
    # --------------------------
    start_date = (datetime.utcnow() + timedelta(days=3)).strftime("%B %d, %Y")
    end_date = (datetime.utcnow() + timedelta(days=7)).strftime("%B %d, %Y")
    estimated_delivery = f"{start_date} - {end_date}"

    # --------------------------
    # 7️⃣ Build response for UI
    # --------------------------
    response = PlaceOrderResponse(
        order_id=order.id,
        estimated_delivery=estimated_delivery,
        message="Thank you for your order! A confirmation email has been sent.",
        items=placed_items,
        subtotal=order.subtotal,
        shipping=order.shipping,
        tax=order.tax,
        total=order.total,
        track_order_url=f"/orders/{order.id}",
        continue_shopping_url="/books",
        invoice_url=f"/orders/{order.id}/invoice",
    )

    return response


#After checkout confirm  

@router.get("/order/confirm/{order_id}")
def get_order_confirmation(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()

    # Format order_id like #123
    display_order_id = f"#{order.id}"

    # Delivery estimate
    start = (order.created_at + timedelta(days=3)).strftime("%B %d, %Y")
    end = (order.created_at + timedelta(days=7)).strftime("%B %d, %Y")
    estimate = f"{start} - {end}"

    return {
        "order_id": display_order_id,
        "status": order.status,
        "estimated_delivery": estimate,
        "subtotal": order.subtotal,
        "shipping": order.shipping,
        "tax": order.tax,
        "total": order.total,
        "items": items,
        "message":"Order confirmed"
    }


@router.post("/orders/{order_id}/payment/complete")
def complete_payment(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    order.status = "paid"
    session.commit()

    return {
        "message": "Payment successful",
        "order_id": order_id,
        "track_order_url": f"/orders/{order_id}/track"
    }

# Track Orders

@router.get("/orders/{order_id}/track")
def track_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    return {
        "order_id": f"#{order.id}",
        "status": order.status,  # processing, shipped, out_for_delivery, delivered
        "created_at": order.created_at,
    }

#Download Invoice

@router.get("/orders/{order_id}/invoice")
def download_invoice(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    order = session.get(Order, order_id)

    if not order or order.user_id != current_user.id:
        raise HTTPException(404, "Order not found")

    file_path = f"invoices/invoice_{order.id}.pdf"

    # Generate if missing
    if not os.path.exists(file_path):
        generate_invoice_pdf(order, session, file_path)

    return FileResponse(
        file_path,
        filename=f"invoice_{order.id}.pdf",
        media_type="application/pdf"
    )



def generate_invoice_pdf(order, session, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    c = canvas.Canvas(file_path)
    c.drawString(100, 750, f"Invoice for Order #{order.id}")
    c.drawString(100, 720, f"Total: {order.total}")
    c.drawString(100, 700, f"Date: {order.created_at}")

    c.save()
