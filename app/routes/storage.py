"""
FastAPI with Cloudflare R2 Storage Integration
Install required packages: pip install fastapi boto3 python-multipart uvicorn python-dotenv
"""

import select
from fastapi import FastAPI, Query, UploadFile, File, HTTPException , APIRouter
from fastapi.params import Depends
from fastapi.responses import StreamingResponse
import boto3
from botocore.exceptions import ClientError
from typing import List
import io
import os
from datetime import datetime
from dotenv import load_dotenv
from functools import lru_cache
import time

from requests import Session
from app.database import get_session
from app.models.user import User
from app.utils.pagination import paginate
from app.utils.token import get_current_admin

# Load environment variables from .env file
load_dotenv()

router = APIRouter()
CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket() -> int:
    """
    Changes every 60 minutes → auto cache expiry
    """
    return int(time.time() // CACHE_TTL)

def clear_r2_cache():
    _cached_list_by_folder.cache_clear()
    _cached_file_info.cache_clear()
    _cached_presigned_url.cache_clear()


# R2 Configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

# Validate that all required environment variables are set
if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
    raise ValueError(
        "Missing required environment variables. Please set:\n"
        "R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME"
    )

# Initialize S3 client for R2
s3_client = boto3.client(
    's3',
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name='auto'
)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = ""
):
    """Upload a file to R2 storage with optional folder path"""
    try:
        # Read file content
        contents = await file.read()
        
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        
        # Construct the full path with folder
        if folder:
            # Remove leading/trailing slashes and ensure proper format
            folder = folder.strip("/")
            file_key = f"{folder}/{filename}"
        else:
            file_key = filename
        
        # Upload to R2
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=file_key,
            Body=contents,
            ContentType=file.content_type
        )
        clear_r2_cache()
        
        return {
            "message": "File uploaded successfully",
            "filename": file.filename,
            "key": file_key,
            "folder": folder or "root",
            "size": len(contents)
        }
    
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-multiple")
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    """Upload multiple files to R2 storage"""
    uploaded_files = []
    
    for file in files:
        try:
            contents = await file.read()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_key = f"{timestamp}_{file.filename}"
            
            s3_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=file_key,
                Body=contents,
                ContentType=file.content_type
            )
            
            uploaded_files.append({
                "filename": file.filename,
                "key": file_key,
                "size": len(contents)
            })
        
        except ClientError as e:
            uploaded_files.append({
                "filename": file.filename,
                "error": str(e)
            })
    clear_r2_cache()
    return {"uploaded_files": uploaded_files}


@router.get("/download/{file_key:path}")
async def download_file(file_key: str):
    """Download a file from R2 storage"""
    try:
        # Get object from R2
        response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=file_key)
        
        # Stream the file
        return StreamingResponse(
            io.BytesIO(response['Body'].read()),
            media_type=response.get('ContentType', 'application/octet-stream'),
            headers={
                "Content-Disposition": f"attachment; filename={file_key.split('/')[-1]}"
            }
        )
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


    

    files = []
    if "Contents" in response:
        for obj in response["Contents"]:
            files.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat()
            })

    return {
        "files": files,
        "count": len(files)
    }


@router.get("/list")
def list_files(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin),
):
    query = select(File).order_by(File.created_at.desc())

    return paginate(session=session, query=query, page=page, limit=limit)



@router.delete("/delete/{file_key:path}")
async def delete_file(file_key: str):
    
    """Delete a file from R2 storage"""
    try:
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=file_key)
        clear_r2_cache()
        return {"message": "File deleted successfully", "key": file_key}
    
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@lru_cache(maxsize=512)
def _cached_file_info(file_key: str, bucket: int):
    response = s3_client.head_object(
        Bucket=R2_BUCKET_NAME,
        Key=file_key
    )

    return {
        "key": file_key,
        "size": response["ContentLength"],
        "content_type": response.get("ContentType"),
        "last_modified": response["LastModified"].isoformat(),
        "etag": response["ETag"]
    }


@router.get("/file-info/{file_key:path}")
async def get_file_info(file_key: str):
    try:
        return _cached_file_info(file_key, _ttl_bucket())
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            raise HTTPException(404, "File not found")
        raise HTTPException(500, str(e))
    
@lru_cache(maxsize=512)
def _cached_presigned_url(file_key: str, expiration: int, bucket: int):
    return {
        "url": s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": file_key},
            ExpiresIn=expiration
        ),
        "expires_in_seconds": expiration
    }


@router.get("/generate-presigned-url/{file_key:path}")
async def generate_presigned_url(file_key: str, expiration: int = 3600):
    try:
        return _cached_presigned_url(file_key, expiration, _ttl_bucket())
    except ClientError as e:
        raise HTTPException(500, str(e))

@router.post("/upload-by-type")
async def upload_file_by_type(
    file: UploadFile = File(...),
    file_type: str = "general"
):
    """
    Upload a file and automatically organize by type
    file_type options: book_covers, profile_pictures, documents, general
    """
    try:
        # Define folder structure based on file type
        folder_mapping = {
            "book_covers": "uploads/book_covers",
            "profile_pictures": "uploads/profiles",
            "documents": "uploads/documents",
            "invoices": "uploads/invoices",
            "general": "uploads/general"
        }
        
        # Get the folder path
        folder = folder_mapping.get(file_type, "uploads/general")
        
        # Read file content
        contents = await file.read()
        
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        
        # Construct the full path
        file_key = f"{folder}/{filename}"
        
        # Upload to R2
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=file_key,
            Body=contents,
            ContentType=file.content_type
        )
        clear_r2_cache()
        return {
            "message": "File uploaded successfully",
            "filename": file.filename,
            "key": file_key,
            "folder": folder,
            "type": file_type,
            "size": len(contents)
        }
    
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-book-cover")
async def upload_book_cover(file: UploadFile = File(...), book_id: int = None):
    """Specifically for uploading book covers"""
    try:
        contents = await file.read()
        
        # Use book_id in filename if provided
        if book_id:
            filename = f"book_{book_id}_{file.filename}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{file.filename}"
        
        file_key = f"uploads/book_covers/{filename}"
        
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=file_key,
            Body=contents,
            ContentType=file.content_type
        )
        clear_r2_cache()
        
        return {
            "message": "Book cover uploaded successfully",
            "filename": file.filename,
            "key": file_key,
            "book_id": book_id,
            "size": len(contents)
        }
    
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@lru_cache(maxsize=256)
def _cached_list_by_folder(folder: str, max_keys: int, bucket: int):
    prefix = folder.strip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    response = s3_client.list_objects_v2(
        Bucket=R2_BUCKET_NAME,
        Prefix=prefix,
        MaxKeys=max_keys
    )

    files = []
    if "Contents" in response:
        for obj in response["Contents"]:
            files.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat()
            })

    return {
        "folder": folder or "root",
        "files": files,
        "count": len(files)
    }

@router.get("/list-by-folder")
async def list_files_by_folder(folder: str = "", max_keys: int = 100):
    return _cached_list_by_folder(folder, max_keys, _ttl_bucket())

    
@router.post("/upload-from-path")    
async def upload_file_from_path(file_path: str):
    """Upload a file from local file system path to R2"""
    try:
        # Normalize the path to handle Windows backslashes
        normalized_path = os.path.normpath(file_path)
        
        if not os.path.exists(normalized_path):
            raise HTTPException(status_code=404, detail="File not found on local system")
        
        # Read file
        with open(normalized_path, 'rb') as f:
            contents = f.read()
        
        # Get filename and create key
        filename = os.path.basename(normalized_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_key = f"{timestamp}_{filename}"
        
        # Detect content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(normalized_path)
        
        # Upload to R2
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=file_key,
            Body=contents,
            ContentType=content_type or 'application/octet-stream'
        )
        clear_r2_cache()
        return {
            "message": "File uploaded successfully",
            "filename": filename,
            "key": file_key,
            "size": len(contents)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
