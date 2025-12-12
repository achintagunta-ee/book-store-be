import os
import boto3
from dotenv import load_dotenv


load_dotenv()


R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE") 

s3_client = boto3.client(
    "s3",
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto"
)


# app/services/r2_client.py

def upload_to_r2(file, key: str, content_type: str):
    s3_client.upload_fileobj(
        file,
        R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type}
    )
    return key


def delete_from_r2(key: str):
    try:
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
    except Exception:
        pass
