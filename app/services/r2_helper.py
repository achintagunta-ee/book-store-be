# app/services/r2_helper.py
import time
from fastapi import UploadFile
from slugify import slugify
from app.services.r2_client import s3_client, R2_BUCKET_NAME

def upload_book_cover(file: UploadFile, title: str):
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

def to_presigned_url(key: str, expires=3600):
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires
    )
def upload_profile_image(file: UploadFile, user_id: int):
    ext = file.filename.split(".")[-1]
    key = f"profiles/user_{user_id}.{ext}"

    s3_client.upload_fileobj(
        file.file,
        R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": file.content_type}
    )
    return key

def upload_site_logo(file: UploadFile):
    ext = file.filename.split(".")[-1].lower()
    filename = f"site_logo_{int(time.time())}.{ext}"
    key = f"settings/{filename}"

    s3_client.upload_fileobj(
        file.file,
        R2_BUCKET_NAME,
        key,
        ExtraArgs={
            "ContentType": file.content_type,
            "ACL": "private"  # keep private → presigned URL
        }
    )
    return key