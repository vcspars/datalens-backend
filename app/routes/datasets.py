"""Dataset routes"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from app.database import get_database
from app.schemas.dataset import DatasetResponse, DatasetListResponse
from app.models.dataset import Dataset
from app.routes.auth import get_current_user
from app.models.user import User
from app.services.google_drive import drive_service
from app.services.local_storage import local_storage
from bson import ObjectId
from datetime import datetime
import math


router = APIRouter(prefix="/datasets", tags=["datasets"])


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


@router.post("/upload/csv", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Upload a CSV file"""
    try:
        # Validate file type
        if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only CSV and Excel files are supported."
            )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size (50MB limit)
        if file_size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 50MB limit"
            )
        
        # Determine MIME type
        mime_type = "text/csv"
        if file.filename.endswith('.xlsx'):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif file.filename.endswith('.xls'):
            mime_type = "application/vnd.ms-excel"
        
        # Try Google Drive first, fallback to local storage
        drive_file_id = None
        use_local_storage = False
        storage_location = "unknown"
        
        if drive_service.service and drive_service.base_folder_id:
            try:
                print(f"[UPLOAD] Attempting Google Drive upload for user {current_user._id}")
                # Create user folder in Google Drive
                user_folder_id = drive_service.create_user_folder(str(current_user._id))
                print(f"[UPLOAD] Created/found user folder in Google Drive: {user_folder_id}")
                
                # Upload to Google Drive
                drive_file_id = drive_service.upload_file(
                    file_content=file_content,
                    file_name=file.filename,
                    mime_type=mime_type,
                    folder_id=user_folder_id
                )
                print(f"[UPLOAD] ✓ Successfully uploaded to Google Drive. File ID: {drive_file_id}")
                storage_location = "google_drive"
            except Exception as e:
                error_msg = str(e)
                print(f"[UPLOAD] Google Drive upload failed: {error_msg}")
                # If it's a storage quota error, use local storage
                if 'storageQuotaExceeded' in error_msg or 'quota' in error_msg.lower() or 'cannot store files' in error_msg.lower():
                    print(f"[UPLOAD] Quota error detected, falling back to local storage")
                    use_local_storage = True
                else:
                    print(f"[UPLOAD] Other error, will try local storage as fallback")
                    use_local_storage = True
        else:
            print(f"[UPLOAD] Google Drive not available (service={drive_service.service is not None}, base_folder={drive_service.base_folder_id}), using local storage")
            use_local_storage = True
        
        if not drive_file_id or use_local_storage:
            # Use local storage as fallback
            print(f"[UPLOAD] Storing file locally...")
            user_folder_path = local_storage.create_user_folder(str(current_user._id))
            drive_file_id = local_storage.upload_file(
                file_content=file_content,
                file_name=file.filename,
                mime_type=mime_type,
                folder_path=user_folder_path
            )
            print(f"[UPLOAD] ✓ File stored locally: {drive_file_id}")
            storage_location = "local"
        
        # Save dataset metadata to MongoDB
        db = get_database()
        dataset = Dataset(
            user_id=str(current_user._id),
            name=name,
            dataset_type="csv",
            google_drive_file_id=drive_file_id,
            file_name=file.filename,
            file_size=file_size,
            description=description
        )
        
        result = await db.datasets.insert_one(dataset.to_dict())
        
        return DatasetResponse(
            id=str(result.inserted_id),
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            file_name=dataset.file_name,
            file_size=dataset.file_size,
            description=dataset.description,
            uploaded_at=dataset.created_at,
            size=format_file_size(dataset.file_size)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading CSV: {str(e)}"
        )


@router.post("/upload/pdf", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Upload a PDF file"""
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only PDF files are supported."
            )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size (25MB limit)
        if file_size > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 25MB limit"
            )
        
        # Try Google Drive first, fallback to local storage
        drive_file_id = None
        use_local_storage = False
        storage_location = "unknown"
        
        if drive_service.service and drive_service.base_folder_id:
            try:
                print(f"[UPLOAD] Attempting Google Drive upload for user {current_user._id}")
                # Create user folder in Google Drive
                user_folder_id = drive_service.create_user_folder(str(current_user._id))
                print(f"[UPLOAD] Created/found user folder in Google Drive: {user_folder_id}")
                
                # Upload to Google Drive
                drive_file_id = drive_service.upload_file(
                    file_content=file_content,
                    file_name=file.filename,
                    mime_type="application/pdf",
                    folder_id=user_folder_id
                )
                print(f"[UPLOAD] ✓ Successfully uploaded to Google Drive. File ID: {drive_file_id}")
                storage_location = "google_drive"
            except Exception as e:
                error_msg = str(e)
                print(f"[UPLOAD] Google Drive upload failed: {error_msg}")
                # If it's a storage quota error, use local storage
                if 'storageQuotaExceeded' in error_msg or 'quota' in error_msg.lower() or 'cannot store files' in error_msg.lower():
                    print(f"[UPLOAD] Quota error detected, falling back to local storage")
                    use_local_storage = True
                else:
                    print(f"[UPLOAD] Other error, will try local storage as fallback")
                    use_local_storage = True
        else:
            print(f"[UPLOAD] Google Drive not available (service={drive_service.service is not None}, base_folder={drive_service.base_folder_id}), using local storage")
            use_local_storage = True
        
        if not drive_file_id or use_local_storage:
            # Use local storage as fallback
            print(f"[UPLOAD] Storing file locally...")
            user_folder_path = local_storage.create_user_folder(str(current_user._id))
            drive_file_id = local_storage.upload_file(
                file_content=file_content,
                file_name=file.filename,
                mime_type="application/pdf",
                folder_path=user_folder_path
            )
            print(f"[UPLOAD] ✓ File stored locally: {drive_file_id}")
            storage_location = "local"
        
        # Save dataset metadata to MongoDB
        db = get_database()
        dataset = Dataset(
            user_id=str(current_user._id),
            name=name,
            dataset_type="pdf",
            google_drive_file_id=drive_file_id,
            file_name=file.filename,
            file_size=file_size,
            description=description
        )
        
        result = await db.datasets.insert_one(dataset.to_dict())
        
        return DatasetResponse(
            id=str(result.inserted_id),
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            file_name=dataset.file_name,
            file_size=dataset.file_size,
            description=dataset.description,
            uploaded_at=dataset.created_at,
            size=format_file_size(dataset.file_size)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading PDF: {str(e)}"
        )


@router.get("/", response_model=DatasetListResponse)
async def get_datasets(current_user: User = Depends(get_current_user)):
    """Get all datasets for the current user"""
    try:
        db = get_database()
        cursor = db.datasets.find({"user_id": str(current_user._id)})
        datasets = await cursor.to_list(length=100)
        
        dataset_list = [
            DatasetResponse(
                id=str(d["_id"]),
                name=d["name"],
                dataset_type=d["dataset_type"],
                file_name=d["file_name"],
                file_size=d["file_size"],
                description=d.get("description"),
                uploaded_at=d["created_at"],
                size=format_file_size(d["file_size"])
            )
            for d in datasets
        ]
        
        return DatasetListResponse(datasets=dataset_list, total=len(dataset_list))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching datasets: {str(e)}"
        )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: str, current_user: User = Depends(get_current_user)):
    """Get a specific dataset"""
    try:
        db = get_database()
        dataset_data = await db.datasets.find_one({
            "_id": ObjectId(dataset_id),
            "user_id": str(current_user._id)
        })
        
        if not dataset_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        
        dataset = Dataset.from_dict(dataset_data)
        return DatasetResponse(
            id=str(dataset._id),
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            file_name=dataset.file_name,
            file_size=dataset.file_size,
            description=dataset.description,
            uploaded_at=dataset.created_at,
            size=format_file_size(dataset.file_size)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dataset: {str(e)}"
        )


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: str, current_user: User = Depends(get_current_user)):
    """Delete a dataset"""
    try:
        db = get_database()
        dataset_data = await db.datasets.find_one({
            "_id": ObjectId(dataset_id),
            "user_id": str(current_user._id)
        })
        
        if not dataset_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        
        # Delete from storage (Google Drive or local)
        try:
            file_id = dataset_data["google_drive_file_id"]
            # Try Google Drive first
            if drive_service.service:
                try:
                    drive_service.delete_file(file_id)
                except:
                    # If Google Drive delete fails, try local storage
                    local_storage.delete_file(file_id)
            else:
                local_storage.delete_file(file_id)
        except Exception as e:
            # Log error but continue with MongoDB deletion
            print(f"Warning: Could not delete file from storage: {e}")
        
        # Delete from MongoDB
        await db.datasets.delete_one({"_id": ObjectId(dataset_id)})
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting dataset: {str(e)}"
        )

