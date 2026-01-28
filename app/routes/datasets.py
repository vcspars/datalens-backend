"""Dataset routes"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from app.database import get_database
from app.schemas.dataset import DatasetResponse, DatasetListResponse, ColumnCalculationRequest, SaveChangesRequest
from app.models.dataset import Dataset
from app.routes.auth import get_current_user
from app.models.user import User
from app.services.google_drive import drive_service
from app.services.local_storage import local_storage
from bson import ObjectId
from datetime import datetime
import math
import csv
import io
import pandas as pd


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
            # Determine dataset type from file extension
            file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else 'csv'
            user_folder_path = local_storage.create_user_folder(str(current_user._id), dataset_type=file_ext)
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
            user_folder_path = local_storage.create_user_folder(str(current_user._id), dataset_type="pdf")
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


@router.get("/{dataset_id}/data")
async def get_dataset_data(
    dataset_id: str,
    limit: int = None,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get CSV/Excel data for a dataset"""
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
        
        if dataset_data["dataset_type"] not in ["csv", "xls", "xlsx"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only supports CSV and Excel files"
            )
        
        # Get file content
        file_id = dataset_data["google_drive_file_id"]
        file_content = None
        
        # Try to get from Google Drive first
        if drive_service.service:
            try:
                file_content = drive_service.download_file(file_id)
            except:
                pass
        
        # Fallback to local storage
        if not file_content:
            try:
                file_content = local_storage.download_file(file_id)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found in storage: {str(e)}"
                )
        
        # Parse CSV/Excel file
        file_name = dataset_data["file_name"]
        df = None
        
        try:
            if file_name.endswith('.csv'):
                # Read CSV - try multiple encodings
                encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                df = None
                for encoding in encodings:
                    try:
                        # Read full file if no limit specified
                        if limit is None:
                            df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                        else:
                            df = pd.read_csv(io.BytesIO(file_content), encoding=encoding, nrows=limit + offset if offset > 0 else limit)
                        break
                    except UnicodeDecodeError:
                        continue
                if df is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Could not decode CSV file with any supported encoding"
                    )
            elif file_name.endswith(('.xlsx', '.xls')):
                # Read Excel - full file if no limit specified
                if limit is None:
                    df = pd.read_excel(io.BytesIO(file_content))
                else:
                    df = pd.read_excel(io.BytesIO(file_content), nrows=limit + offset if offset > 0 else limit)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported file format"
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing file: {str(e)}"
            )
        
        # Store total rows before pagination
        total_rows = len(df)
        
        # Apply pagination only if limit is specified
        if limit is not None:
            if offset > 0:
                df = df.iloc[offset:]
            df = df.head(limit)
        
        # Convert to JSON
        # Replace NaN with null for JSON serialization
        df = df.fillna("")
        
        # Get columns
        columns = df.columns.tolist()
        
        # Convert to records (list of dictionaries)
        records = df.to_dict('records')
        
        return {
            "columns": columns,
            "data": records,
            "total_rows": total_rows,  # Return total rows in file, not just returned rows
            "returned_rows": len(records),  # Rows actually returned
            "total_columns": len(columns)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dataset data: {str(e)}"
        )


@router.post("/{dataset_id}/column/calculate")
async def calculate_column_statistic(
    dataset_id: str,
    request_data: ColumnCalculationRequest,
    current_user: User = Depends(get_current_user)
):
    """Calculate statistics for a column"""
    try:
        column_name = request_data.column_name
        operation = request_data.operation
        
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
        
        if dataset_data["dataset_type"] not in ["csv", "xls", "xlsx"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only supports CSV and Excel files"
            )
        
        # Get file content
        file_id = dataset_data["google_drive_file_id"]
        file_content = None
        
        # Try to get from Google Drive first
        if drive_service.service:
            try:
                file_content = drive_service.download_file(file_id)
            except:
                pass
        
        # Fallback to local storage
        if not file_content:
            try:
                file_content = local_storage.download_file(file_id)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found in storage: {str(e)}"
                )
        
        # Parse CSV/Excel file
        file_name = dataset_data["file_name"]
        df = None
        
        try:
            if file_name.endswith('.csv'):
                encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                for encoding in encodings:
                    try:
                        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                if df is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Could not decode CSV file"
                    )
            elif file_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file_content))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing file: {str(e)}"
            )
        
        # Check if column exists
        if column_name not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{column_name}' not found"
            )
        
        # Get column data (convert to numeric if possible)
        col_data = pd.to_numeric(df[column_name], errors='coerce')
        
        # Remove NaN values for calculations
        col_data_clean = col_data.dropna()
        
        if len(col_data_clean) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column contains no numeric values"
            )
        
        result = {}
        
        # Perform calculation based on operation
        if operation.lower() == "sum":
            result["value"] = float(col_data_clean.sum())
            result["formatted"] = f"{col_data_clean.sum():,.2f}"
        elif operation.lower() == "average" or operation.lower() == "mean":
            result["value"] = float(col_data_clean.mean())
            result["formatted"] = f"{col_data_clean.mean():,.2f}"
        elif operation.lower() == "median":
            result["value"] = float(col_data_clean.median())
            result["formatted"] = f"{col_data_clean.median():,.2f}"
        elif operation.lower() == "min":
            result["value"] = float(col_data_clean.min())
            result["formatted"] = f"{col_data_clean.min():,.2f}"
        elif operation.lower() == "max":
            result["value"] = float(col_data_clean.max())
            result["formatted"] = f"{col_data_clean.max():,.2f}"
        elif operation.lower() == "min/max":
            result["min"] = float(col_data_clean.min())
            result["max"] = float(col_data_clean.max())
            result["formatted"] = f"Min: {col_data_clean.min():,.2f}, Max: {col_data_clean.max():,.2f}"
        elif operation.lower() == "standard deviation" or operation.lower() == "std":
            result["value"] = float(col_data_clean.std())
            result["formatted"] = f"{col_data_clean.std():,.2f}"
        elif operation.lower() == "variance":
            result["value"] = float(col_data_clean.var())
            result["formatted"] = f"{col_data_clean.var():,.2f}"
        elif operation.lower() == "mode":
            mode_values = col_data_clean.mode()
            if len(mode_values) > 0:
                result["value"] = float(mode_values.iloc[0])
                result["formatted"] = f"{mode_values.iloc[0]:,.2f}"
            else:
                result["formatted"] = "No mode found"
        elif operation.lower() == "range":
            result["value"] = float(col_data_clean.max() - col_data_clean.min())
            result["formatted"] = f"{col_data_clean.max() - col_data_clean.min():,.2f}"
        elif operation.lower() == "count unique":
            result["value"] = int(col_data_clean.nunique())
            result["formatted"] = f"{col_data_clean.nunique()}"
        elif operation.lower() == "count":
            result["value"] = int(len(col_data_clean))
            result["formatted"] = f"{len(col_data_clean)}"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported operation: {operation}"
            )
        
        return {
            "column": column_name,
            "operation": operation,
            "result": result,
            "total_values": len(col_data),
            "valid_numeric_values": len(col_data_clean)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating statistic: {str(e)}"
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
        # Validate ObjectId format
        try:
            object_id = ObjectId(dataset_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dataset ID format: {str(e)}"
            )
        
        db = get_database()
        user_id_str = str(current_user._id)
        
        # First check if dataset exists at all
        dataset_data = await db.datasets.find_one({"_id": object_id})
        
        if not dataset_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found"
            )
        
        # Check if user owns this dataset
        if dataset_data.get("user_id") != user_id_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this dataset"
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
        await db.datasets.delete_one({"_id": object_id})
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting dataset: {str(e)}"
        )


@router.post("/{dataset_id}/save-changes")
async def save_dataset_changes(
    dataset_id: str,
    request_data: SaveChangesRequest,
    current_user: User = Depends(get_current_user)
):
    """Save changes to a dataset (columns and data)"""
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
        
        if dataset_data["dataset_type"] not in ["csv", "xls", "xlsx"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only supports CSV and Excel files"
            )
        
        # Get file name to determine format
        file_name = dataset_data.get("file_name", "dataset.csv")
        file_id = dataset_data["google_drive_file_id"]
        
        # Convert data to DataFrame
        df = pd.DataFrame(request_data.data)
        
        # Reorder columns to match request
        if request_data.columns:
            # Ensure all requested columns exist
            existing_cols = [col for col in request_data.columns if col in df.columns]
            missing_cols = [col for col in request_data.columns if col not in df.columns]
            
            # Add missing columns with empty values
            for col in missing_cols:
                df[col] = ""
            
            # Reorder columns
            df = df[request_data.columns]
        
        # Convert DataFrame to bytes
        file_content = None
        mime_type = None
        
        if file_name.endswith('.csv'):
            # Convert to CSV
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False, encoding='utf-8')
            file_content = buffer.getvalue()
            mime_type = "text/csv"
        elif file_name.endswith('.xlsx'):
            # Convert to Excel
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            file_content = buffer.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif file_name.endswith('.xls'):
            # Convert to Excel (old format)
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            file_content = buffer.getvalue()
            mime_type = "application/vnd.ms-excel"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format"
            )
        
        # Save to storage (Google Drive or local)
        # Delete old file and create new one with updated content
        saved = False
        
        # Determine storage type from file_id format
        # Google Drive IDs are typically long alphanumeric strings
        # Local storage uses relative paths like "user_123/csv/file.csv"
        is_google_drive = len(file_id) > 20 and '/' not in file_id
        
        if is_google_drive and drive_service.service:
            # Update Google Drive file
            try:
                # Delete old file
                try:
                    drive_service.service.files().delete(fileId=file_id).execute()
                except:
                    pass  # File might not exist
                
                # Get user folder
                user_folder_id = drive_service.create_user_folder(str(current_user._id))
                
                # Upload new file
                new_file_id = drive_service.upload_file(
                    file_content=file_content,
                    file_name=file_name,
                    mime_type=mime_type,
                    folder_id=user_folder_id
                )
                
                # Update database with new file ID
                await db.datasets.update_one(
                    {"_id": ObjectId(dataset_id)},
                    {"$set": {"google_drive_file_id": new_file_id}}
                )
                saved = True
            except Exception as e:
                print(f"[SAVE] Google Drive save failed: {str(e)}")
        
        # Fallback to local storage
        if not saved:
            try:
                # Delete old file
                try:
                    local_storage.delete_file(file_id)
                except:
                    pass  # File might not exist
                
                # Get user folder path
                file_ext = file_name.lower().split('.')[-1] if '.' in file_name else 'csv'
                user_folder_path = local_storage.create_user_folder(str(current_user._id), dataset_type=file_ext)
                
                # Upload new file
                new_file_id = local_storage.upload_file(
                    file_content=file_content,
                    file_name=file_name,
                    mime_type=mime_type,
                    folder_path=user_folder_path
                )
                
                # Update database with new file ID
                await db.datasets.update_one(
                    {"_id": ObjectId(dataset_id)},
                    {"$set": {"google_drive_file_id": new_file_id}}
                )
                saved = True
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save file: {str(e)}"
                )
        
        # Update file size in database
        file_size = len(file_content)
        await db.datasets.update_one(
            {"_id": ObjectId(dataset_id)},
            {"$set": {"file_size": file_size}}
        )
        
        return {
            "message": "Changes saved successfully",
            "rows_saved": len(request_data.data),
            "columns_saved": len(request_data.columns)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving changes: {str(e)}"
        )

