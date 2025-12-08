from fastapi import APIRouter, UploadFile, File
from app.services.r2_client import s3_client, R2_BUCKET_NAME

router = APIRouter()

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    key = f"images/{file.filename}"

    s3_client.upload_fileobj(
        file.file,
        R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": file.content_type}
    )

    return {"message": "uploaded", "key": key}

@router.get("/file/{key}")
def get_file_url(key: str):
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=3600
    )
    return {"url": url}

@router.delete("/delete/{key}")
def delete_file(key: str):
    s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
    return {"message": "deleted"}
