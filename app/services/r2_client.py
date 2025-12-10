import os
import boto3
from dotenv import load_dotenv

load_dotenv()

R2_ENDPOINT_URL = os.getenv("CLOUDFLARE_R2_BUCKET_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("CLOUDFLARE_R2_ACCESS_KEY")
R2_SECRET_ACCESS_KEY = os.getenv("CLOUDFLARE_R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("CLOUDFLARE_R2_BUCKET")

s3_client = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto"
)
