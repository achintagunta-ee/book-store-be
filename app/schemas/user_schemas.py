from pydantic import BaseModel, EmailStr ,model_validator
import re


class UserRegister(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: EmailStr
    password: str
    confirm_password: str

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if len(self.password) < 8:
            raise ValueError("Password must be at least 8 characters")

        if not re.search(r"[A-Z]", self.password):
            raise ValueError("Must contain uppercase letter")

        if not re.search(r"[a-z]", self.password):
            raise ValueError("Must contain lowercase letter")

        if not re.search(r"\d", self.password):
            raise ValueError("Must contain a number")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", self.password):
            raise ValueError("Must contain special character")
        return self

class UserResponse(BaseModel):
    message: str
    user_id: int
    email: EmailStr
    client: str
    role: str
    can_login: bool

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str



class RazorpayPaymentVerifySchema(BaseModel):
    order_id: int
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
