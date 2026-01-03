# app/routes/test_email.py
from fastapi import APIRouter, BackgroundTasks
from app.services.email_service import send_email

router = APIRouter()

@router.get("/test-email")
def test_email(background_tasks: BackgroundTasks):
    background_tasks.add_task(
        send_email,
        "your_email@gmail.com",
        "SendGrid Test Email",
        "<h3>Email system is working ✅</h3>"
    )
    return {"message": "Email triggered"}
