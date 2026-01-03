import os
from pydantic_settings import BaseSettings
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: str = "5432"

    
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    base_url: str = "https://book.efficientemengineering.com"

    # R2 STORAGE
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    AWS_REGION: str

    # ENVIRONMENT
    ENV: str = "local"

    #Email 
    BREVO_API_KEY: str
    MAIL_FROM: str
    STORE_NAME: str = "Hithabodha Bookstore"
    ADMIN_EMAILS: list[str]

    @property
    def database_url(self):
        encoded_password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg2://{self.postgres_user}:"
            f"{encoded_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()


