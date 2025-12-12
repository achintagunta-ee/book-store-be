# app/services/r2_helper.py
import time
from fastapi import UploadFile
from slugify import slugify
from app.services.r2_client import s3_client, R2_BUCKET_NAME, R2_PUBLIC_BASE


def upload_book_cover(file: UploadFile, title: str):
    """Upload book cover using the book title."""
    ext = file.filename.split(".")[-1]
    filename = f"{slugify(title)}_{int(time.time())}.{ext}"
    key = f"book_covers/{filename}"

    s3_client.upload_fileobj(
        file.file,
        R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": file.content_type}
    )

    return key


def delete_r2_file(key: str):
    try:
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
    except:
        pass


def public_url(key: str):
    return f"{R2_PUBLIC_BASE}/{key}"
