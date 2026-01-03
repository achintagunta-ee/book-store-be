import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from urllib.parse import quote_plus
from dotenv import load_dotenv
import json

load_dotenv()

class Settings(BaseSettings):
    # Database settings
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: str
    
    # JWT settings
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    base_url: str
    
    # R2 STORAGE
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    AWS_REGION: str = "auto"
    
    # ENVIRONMENT
    ENV: str = "local"
    
    # Email 
    BREVO_API_KEY: str
    MAIL_FROM: str
    STORE_NAME: str = "Hithabodha Bookstore"
    
    # Change the type annotation to accept str or list
    ADMIN_EMAILS: str | List[str] = Field(default_factory=list)
    
    @field_validator('ADMIN_EMAILS', mode='before')
    @classmethod
    def parse_admin_emails(cls, v):
        """Parse ADMIN_EMAILS from various formats"""
        if v is None or v == '':
            return []
        
        if isinstance(v, str):
            # Empty string variations
            if v.strip() in ('', '[]', ''):
                return []
            
            # Try parsing as JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [email.strip() for email in parsed if email]
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Fall back to comma-separated values
            return [email.strip() for email in v.split(',') if email.strip()]
        
        # If it's already a list
        if isinstance(v, list):
            return [email.strip() for email in v if email]
        
        return []
    
    @field_validator('access_token_expire_minutes', mode='before')
    @classmethod
    def parse_int_fields(cls, v):
        """Ensure integer fields are properly parsed"""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                raise ValueError(f"access_token_expire_minutes must be a valid integer")
        return v
    
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