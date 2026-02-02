"""Dataset routes"""
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from app.database import get_database
from app.schemas.dataset import (
    DatasetResponse,
    DatasetListResponse,
    ColumnCalculationRequest,
    SaveChangesRequest,
    AddIntelligentColumnRequest,
)
from app.models.dataset import Dataset
from app.routes.auth import get_current_user
from app.models.user import User
from app.services.google_drive import drive_service
from app.services.local_storage import local_storage
from app.services.pdf_generation import generate_pdf_summary_questions_report
from app.config import settings
from bson import ObjectId
from datetime import datetime, date
import asyncio
import math
import csv
import io
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
from openai import OpenAI


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


def generate_dummy_csv_summary(name: str) -> str:
    """Generate dummy summary for CSV dataset"""
    return f"""This CSV dataset "{name}" has been successfully uploaded and processed. The dataset contains structured data that can be analyzed, filtered, and visualized. The data appears to be well-formatted and ready for analysis. You can explore the data through various operations including column calculations, filtering, and data transformations."""

def generate_dummy_csv_questions() -> list[str]:
    """Generate dummy questions for CSV dataset"""
    return [
        "What are the main columns in this dataset?",
        "What is the total number of rows?",
        "What are the key insights from this data?",
        "What patterns can be identified in the data?",
        "What are the summary statistics for numeric columns?"
    ]

def generate_dummy_csv_report(name: str) -> str:
    """Generate dummy report for CSV dataset"""
    return f"""# CSV Dataset Analysis Report

## Dataset Overview
**Dataset Name:** {name}
**Status:** Uploaded and ready for analysis

## Executive Summary
This dataset has been successfully processed and is available for comprehensive analysis. The data is structured and ready for various analytical operations including calculations, filtering, and visualization.

## Data Structure
- Data format: CSV/Excel
- Ready for analysis: Yes
- Data integrity: Verified

## Available Operations
- Column calculations (Sum, Average, Median, Min/Max)
- Data filtering and sorting
- Column operations (Add, Delete, Edit)
- Data visualization
- Statistical analysis

## Next Steps
You can now explore this dataset through the preview interface, perform calculations, and generate insights from your data."""


@router.post("/upload/csv", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
    generate_summary: str = Form("true"),
    generate_questions: str = Form("true"),
    generate_report: str = Form("true"),
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
        
        # Parse generation flags
        gen_summary = generate_summary.lower() == "true"
        gen_questions = generate_questions.lower() == "true"
        gen_report = generate_report.lower() == "true"
        
        # Generate dummy content based on flags
        summary = generate_dummy_csv_summary(name) if gen_summary else None
        questions = generate_dummy_csv_questions() if gen_questions else None
        report = generate_dummy_csv_report(name) if gen_report else None
        
        # Save dataset metadata to MongoDB
        db = get_database()
        dataset = Dataset(
            user_id=str(current_user._id),
            name=name,
            dataset_type="csv",
            google_drive_file_id=drive_file_id,
            file_name=file.filename,
            file_size=file_size,
            description=description,
            summary=summary,
            questions=questions,
            report=report,
            summary_generated=gen_summary,
            questions_generated=gen_questions,
            report_generated=gen_report
        )
        
        result = await db.datasets.insert_one(dataset.to_dict())
        
        return DatasetResponse(
            id=str(result.inserted_id),
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            file_name=dataset.file_name,
            file_size=dataset.file_size,
            description=dataset.description,
            summary=dataset.summary,
            questions=dataset.questions,
            report=dataset.report,
            summary_generated=dataset.summary_generated,
            questions_generated=dataset.questions_generated,
            report_generated=dataset.report_generated,
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


def generate_dummy_summary(name: str) -> str:
    """Generate dummy summary for PDF"""
    return f"""This PDF document "{name}" contains important information and has been successfully uploaded to the system. The document appears to be well-structured and contains multiple sections covering various topics. Key highlights include detailed information that can be analyzed and processed for insights. The document is ready for further analysis and question-answering interactions."""

def generate_dummy_questions() -> list[str]:
    """Generate dummy questions for PDF"""
    return [
        "What are the main topics covered in this document?",
        "Can you summarize the key findings?",
        "What are the recommendations mentioned?",
        "What is the purpose of this document?",
        "Who are the key stakeholders mentioned?"
    ]

def generate_dummy_report(name: str) -> str:
    """Generate dummy report for PDF"""
    return f"""# PDF Analysis Report

## Document Overview
**Document Name:** {name}
**Status:** Uploaded and ready for analysis

## Executive Summary
This document has been successfully processed and is available for comprehensive analysis. The system has extracted the document structure and is ready to answer questions and provide insights.

## Key Sections Identified
- Introduction and context
- Main content sections
- Conclusions and recommendations

## Analysis Status
- Document parsing: Complete
- Text extraction: Complete
- Ready for AI analysis: Yes

## Next Steps
You can now interact with this document through the chat interface to get specific answers and insights."""

@router.post("/upload/pdf", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
    generate_summary: str = Form("true"),
    generate_questions: str = Form("true"),
    generate_report: str = Form("true"),
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
        
        # Parse generation flags
        gen_summary = generate_summary.lower() == "true"
        gen_questions = generate_questions.lower() == "true"
        gen_report = generate_report.lower() == "true"
        
        # Save dataset metadata to MongoDB first (so we have dataset_id for .md storage)
        db = get_database()
        dataset = Dataset(
            user_id=str(current_user._id),
            name=name,
            dataset_type="pdf",
            google_drive_file_id=drive_file_id,
            file_name=file.filename,
            file_size=file_size,
            description=description,
            summary=None,
            questions=None,
            report=None,
            summary_generated=False,
            questions_generated=False,
            report_generated=False,
        )
        
        result = await db.datasets.insert_one(dataset.to_dict())
        dataset_id = str(result.inserted_id)
        
        # If user checked any of summary/questions/report, generate with LangChain + PyMuPDF (3 threads, .md files)
        if gen_summary or gen_questions or gen_report:
            try:
                summary, questions, report = await asyncio.to_thread(
                    generate_pdf_summary_questions_report,
                    file_content,
                    name,
                    str(current_user._id),
                    dataset_id,
                )
                await db.datasets.update_one(
                    {"_id": ObjectId(dataset_id)},
                    {
                        "$set": {
                            "summary": summary,
                            "questions": questions,
                            "report": report,
                            "summary_generated": gen_summary,
                            "questions_generated": gen_questions,
                            "report_generated": gen_report,
                            "updated_at": datetime.utcnow(),
                        }
                    }
                )
            except Exception as e:
                # If generation fails, leave dataset as-is (no summary/questions/report) and don't fail upload
                print(f"[UPLOAD] PDF generation failed: {e}")
        
        # Fetch final dataset for response
        updated_data = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
        final = Dataset.from_dict(updated_data)
        
        return DatasetResponse(
            id=str(final._id),
            name=final.name,
            dataset_type=final.dataset_type,
            file_name=final.file_name,
            file_size=final.file_size,
            description=final.description,
            summary=final.summary,
            questions=final.questions,
            report=final.report,
            summary_generated=final.summary_generated,
            questions_generated=final.questions_generated,
            report_generated=final.report_generated,
            uploaded_at=final.created_at,
            size=format_file_size(final.file_size)
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
                summary=d.get("summary"),
                questions=d.get("questions"),
                report=d.get("report"),
                summary_generated=d.get("summary_generated", False),
                questions_generated=d.get("questions_generated", False),
                report_generated=d.get("report_generated", False),
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


@router.get("/{dataset_id}/download")
async def download_dataset_file(
    dataset_id: str,
    current_user: User = Depends(get_current_user)
):
    """Download a dataset file (PDF, CSV, Excel)"""
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
        
        # Get file content
        file_id = dataset_data["google_drive_file_id"]
        file_content = None
        file_name = dataset_data["file_name"]
        
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
        
        # Determine content type based on file extension
        content_type_map = {
            '.pdf': 'application/pdf',
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel'
        }
        
        content_type = 'application/octet-stream'
        for ext, ct in content_type_map.items():
            if file_name.lower().endswith(ext):
                content_type = ct
                break
        
        # For PDFs, use inline disposition so they can be viewed in browser
        # For other files, use attachment to download
        disposition = 'inline' if content_type == 'application/pdf' else 'attachment'
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{file_name}"',
                "Content-Type": content_type
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading file: {str(e)}"
        )


@router.get("/{dataset_id}/extract-text")
async def extract_pdf_text(
    dataset_id: str,
    current_user: User = Depends(get_current_user)
):
    """Extract text from a PDF file"""
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
        
        if dataset_data["dataset_type"] != "pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only supports PDF files"
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
        
        # Extract text using PyPDF2 or pdfplumber
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            extracted_text = ""
            header_footer_patterns = []
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                # Store first page text as potential header/footer patterns
                if page_num == 0:
                    lines = page_text.split('\n')
                    if len(lines) > 0:
                        # Get first few lines as potential header
                        header_footer_patterns.extend([line.strip() for line in lines[:3] if line.strip()])
                
                extracted_text += f"\n--- Page {page_num + 1} ---\n"
                extracted_text += page_text
            
            return {
                "text": extracted_text,
                "total_pages": len(pdf_reader.pages),
                "dataset_id": dataset_id,
                "note": "Text extracted as-is from PDF. Duplicate text at bottom may be from PDF structure (headers/footers)."
            }
        except ImportError:
            # Fallback: try pdfplumber
            try:
                import pdfplumber
                extracted_text = ""
                total_pages = 0
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    total_pages = len(pdf.pages)
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text() or ""
                        extracted_text += f"\n--- Page {page_num + 1} ---\n"
                        extracted_text += page_text
                
                return {
                    "text": extracted_text,
                    "total_pages": total_pages,
                    "dataset_id": dataset_id,
                    "note": "Text extracted as-is from PDF. Duplicate text at bottom may be from PDF structure (headers/footers)."
                }
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="PDF extraction libraries (PyPDF2 or pdfplumber) not installed"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error extracting text from PDF: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting PDF text: {str(e)}"
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
        
        # "count unique" can work on any column (numeric or not)
        if operation.lower() == "count unique":
            raw_col = df[column_name].dropna()
            if len(col_data_clean) > 0:
                result = {"value": int(col_data_clean.nunique()), "formatted": str(col_data_clean.nunique())}
                valid_count = len(col_data_clean)
            else:
                result = {"value": int(raw_col.nunique()), "formatted": str(raw_col.nunique())}
                valid_count = len(raw_col)
            return {
                "column": column_name,
                "operation": operation,
                "result": result,
                "total_values": len(df[column_name]),
                "valid_numeric_values": valid_count,
            }
        
        if len(col_data_clean) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column contains no numeric values"
            )
        
        result = {}
        
        # Perform calculation based on operation
        if operation.lower() == "percentiles":
            q25 = float(col_data_clean.quantile(0.25))
            q50 = float(col_data_clean.quantile(0.50))
            q75 = float(col_data_clean.quantile(0.75))
            result["p25"] = q25
            result["p50"] = q50
            result["p75"] = q75
            result["formatted"] = f"25th: {q25:,.2f}, 50th: {q50:,.2f}, 75th: {q75:,.2f}"
        elif operation.lower() == "sum":
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
            summary=dataset.summary,
            questions=dataset.questions,
            report=dataset.report,
            summary_generated=dataset.summary_generated,
            questions_generated=dataset.questions_generated,
            report_generated=dataset.report_generated,
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


@router.post("/{dataset_id}/generate/summary", response_model=DatasetResponse)
async def generate_summary(
    dataset_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate summary for a dataset (PDF or CSV). For PDF uses LangChain + PyMuPDF and writes .md files."""
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
        
        if dataset.dataset_type == "csv":
            summary = generate_dummy_csv_summary(dataset.name)
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$set": {"summary": summary, "summary_generated": True, "updated_at": datetime.utcnow()}}
            )
        else:
            # PDF: get file content, run LangChain + PyMuPDF (summary, questions, report in 3 threads), write .md
            file_id = dataset_data["google_drive_file_id"]
            file_content = None
            if drive_service.service:
                try:
                    file_content = drive_service.download_file(file_id)
                except Exception:
                    file_content = None
            if not file_content:
                try:
                    file_content = local_storage.download_file(file_id)
                except Exception:
                    pass
            if not file_content:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load PDF file.")
            summary, questions, report = await asyncio.to_thread(
                generate_pdf_summary_questions_report,
                file_content,
                dataset.name,
                str(current_user._id),
                dataset_id,
            )
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {
                    "$set": {
                        "summary": summary,
                        "questions": questions,
                        "report": report,
                        "summary_generated": True,
                        "questions_generated": True,
                        "report_generated": True,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )
        
        # Return updated dataset
        updated_data = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
        updated_dataset = Dataset.from_dict(updated_data)
        
        return DatasetResponse(
            id=str(updated_dataset._id),
            name=updated_dataset.name,
            dataset_type=updated_dataset.dataset_type,
            file_name=updated_dataset.file_name,
            file_size=updated_dataset.file_size,
            description=updated_dataset.description,
            summary=updated_dataset.summary,
            questions=updated_dataset.questions,
            report=updated_dataset.report,
            summary_generated=updated_dataset.summary_generated,
            questions_generated=updated_dataset.questions_generated,
            report_generated=updated_dataset.report_generated,
            uploaded_at=updated_dataset.created_at,
            size=format_file_size(updated_dataset.file_size)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {str(e)}"
        )


@router.post("/{dataset_id}/generate/questions", response_model=DatasetResponse)
async def generate_questions(
    dataset_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate questions for a dataset (PDF or CSV). For PDF uses LangChain + PyMuPDF and writes .md files."""
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
        
        if dataset.dataset_type == "csv":
            questions = generate_dummy_csv_questions()
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$set": {"questions": questions, "questions_generated": True, "updated_at": datetime.utcnow()}}
            )
        else:
            file_id = dataset_data["google_drive_file_id"]
            file_content = None
            if drive_service.service:
                try:
                    file_content = drive_service.download_file(file_id)
                except Exception:
                    file_content = None
            if not file_content:
                try:
                    file_content = local_storage.download_file(file_id)
                except Exception:
                    pass
            if not file_content:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load PDF file.")
            summary, questions, report = await asyncio.to_thread(
                generate_pdf_summary_questions_report,
                file_content,
                dataset.name,
                str(current_user._id),
                dataset_id,
            )
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {
                    "$set": {
                        "summary": summary,
                        "questions": questions,
                        "report": report,
                        "summary_generated": True,
                        "questions_generated": True,
                        "report_generated": True,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )
        
        # Return updated dataset
        updated_data = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
        updated_dataset = Dataset.from_dict(updated_data)
        
        return DatasetResponse(
            id=str(updated_dataset._id),
            name=updated_dataset.name,
            dataset_type=updated_dataset.dataset_type,
            file_name=updated_dataset.file_name,
            file_size=updated_dataset.file_size,
            description=updated_dataset.description,
            summary=updated_dataset.summary,
            questions=updated_dataset.questions,
            report=updated_dataset.report,
            summary_generated=updated_dataset.summary_generated,
            questions_generated=updated_dataset.questions_generated,
            report_generated=updated_dataset.report_generated,
            uploaded_at=updated_dataset.created_at,
            size=format_file_size(updated_dataset.file_size)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating questions: {str(e)}"
        )


@router.post("/{dataset_id}/generate/report", response_model=DatasetResponse)
async def generate_report(
    dataset_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate report for a dataset (PDF or CSV). For PDF uses LangChain + PyMuPDF and writes .md files."""
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
        
        if dataset.dataset_type == "csv":
            report = generate_dummy_csv_report(dataset.name)
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$set": {"report": report, "report_generated": True, "updated_at": datetime.utcnow()}}
            )
        else:
            file_id = dataset_data["google_drive_file_id"]
            file_content = None
            if drive_service.service:
                try:
                    file_content = drive_service.download_file(file_id)
                except Exception:
                    file_content = None
            if not file_content:
                try:
                    file_content = local_storage.download_file(file_id)
                except Exception:
                    pass
            if not file_content:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load PDF file.")
            summary, questions, report = await asyncio.to_thread(
                generate_pdf_summary_questions_report,
                file_content,
                dataset.name,
                str(current_user._id),
                dataset_id,
            )
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {
                    "$set": {
                        "summary": summary,
                        "questions": questions,
                        "report": report,
                        "summary_generated": True,
                        "questions_generated": True,
                        "report_generated": True,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )
        
        # Return updated dataset
        updated_data = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
        updated_dataset = Dataset.from_dict(updated_data)
        
        return DatasetResponse(
            id=str(updated_dataset._id),
            name=updated_dataset.name,
            dataset_type=updated_dataset.dataset_type,
            file_name=updated_dataset.file_name,
            file_size=updated_dataset.file_size,
            description=updated_dataset.description,
            summary=updated_dataset.summary,
            questions=updated_dataset.questions,
            report=updated_dataset.report,
            summary_generated=updated_dataset.summary_generated,
            questions_generated=updated_dataset.questions_generated,
            report_generated=updated_dataset.report_generated,
            uploaded_at=updated_dataset.created_at,
            size=format_file_size(updated_dataset.file_size)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
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


def _process_chunk_gpt(
    start_idx: int,
    row_chunk: list[tuple],
    prompt: str,
    system_content: str,
    api_key: str,
) -> tuple[int, list[str]]:
    """Sync helper: call OpenAI for one chunk of rows. Used from ThreadPoolExecutor."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env")
    client = OpenAI(api_key=api_key)
    row_lines = "\n".join(
        "\t".join(str(v) if v is not None and str(v) != "nan" else "" for v in row)
        for row in row_chunk
    )
    user_content = f"{prompt}\n\nRow data (one row per line, values separated by tab):\n{row_lines}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    text = (response.choices[0].message.content or "").strip()
    vals = [line.strip() for line in text.split("\n") if line.strip()]
    while len(vals) < len(row_chunk):
        vals.append("")
    return (start_idx, vals[: len(row_chunk)])


def _load_full_dataframe(file_content: bytes, file_name: str) -> pd.DataFrame:
    """Load full CSV/Excel file into a DataFrame (no pagination)."""
    buf = io.BytesIO(file_content)
    if file_name.endswith(".csv"):
        encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
        df = None
        for enc in encodings:
            try:
                buf.seek(0)
                df = pd.read_csv(buf, encoding=enc, on_bad_lines="skip")
                break
            except (UnicodeDecodeError, Exception):
                continue
        if df is None:
            buf.seek(0)
            df = pd.read_csv(buf, encoding="utf-8", on_bad_lines="skip")
    elif file_name.endswith((".xlsx", ".xls")):
        buf.seek(0)
        try:
            df = pd.read_excel(buf, engine="openpyxl")
        except Exception:
            buf.seek(0)
            df = pd.read_excel(buf, engine="xlrd")
    else:
        raise ValueError(f"Unsupported file format: {file_name}")
    return df


def _json_safe_value(v) -> str | int | float | bool | None:
    """Convert a cell value to JSON-serializable type."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        if np.isinf(v):
            return None
        return float(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, date, datetime)):
        return v.isoformat() if hasattr(v, "isoformat") else str(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="ignore")
    return str(v)


@router.post("/{dataset_id}/add-intelligent-column")
async def add_intelligent_column(
    dataset_id: str,
    request_data: AddIntelligentColumnRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an intelligent column using GPT and persist it. Uses concurrent threads for speed."""
    try:
        if not settings.OPENAI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENAI_API_KEY is not set. Add it to .env to use this feature.",
            )
        db = get_database()
        dataset_data = await db.datasets.find_one(
            {"_id": ObjectId(dataset_id), "user_id": str(current_user._id)}
        )
        if not dataset_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
            )
        if dataset_data["dataset_type"] not in ["csv", "xls", "xlsx"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only supports CSV and Excel files",
            )
        file_id = dataset_data["google_drive_file_id"]
        file_name = dataset_data.get("file_name", "dataset.csv")
        file_content = None
        if drive_service.service:
            try:
                file_content = drive_service.download_file(file_id)
            except Exception:
                pass
        if not file_content:
            try:
                file_content = local_storage.download_file(file_id)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found in storage: {str(e)}",
                )
        df = _load_full_dataframe(file_content, file_name)
        source_columns = [c.strip() for c in request_data.source_columns if c.strip()]
        if not source_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one source column is required",
            )
        missing = [c for c in source_columns if c not in df.columns]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source columns not found in dataset: {missing}",
            )
        column_name = (request_data.new_column_name or "").strip()
        if not column_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new_column_name is required",
            )
        column_name = column_name[0].upper() + column_name[1:] if len(column_name) > 1 else column_name.upper()
        if column_name in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A column named '{column_name}' already exists",
            )
        row_data = [
            tuple(df.iloc[i][c] for c in source_columns)
            for i in range(len(df))
        ]
        system_content = (
            "You are a data-transformation assistant. "
            "Return **only** one transformed value per row, each on its own line. No explanations."
        )
        chunk_size = 20
        max_workers = 5
        ordered: dict[int, list[str]] = {}
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    _process_chunk_gpt,
                    i,
                    row_data[i : i + chunk_size],
                    request_data.prompt,
                    system_content,
                    settings.OPENAI_API_KEY,
                )
                for i in range(0, len(row_data), chunk_size)
            ]
            results = await asyncio.gather(*futures)
        for start_idx, vals in results:
            ordered[start_idx] = vals
        new_vals = []
        for i in range(0, len(row_data), chunk_size):
            new_vals.extend(ordered[i])
        if len(new_vals) != len(df):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Row count mismatch: generated {len(new_vals)} values for {len(df)} rows",
            )
        df[column_name] = new_vals
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        df = df.map(_json_safe_value)
        if file_name.endswith(".csv"):
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False, encoding="utf-8")
            file_content_out = buffer.getvalue()
            mime_type = "text/csv"
        elif file_name.endswith((".xlsx", ".xls")):
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            file_content_out = buffer.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format",
            )
        saved = False
        is_google_drive = len(file_id) > 20 and "/" not in file_id
        if is_google_drive and drive_service.service:
            try:
                try:
                    drive_service.service.files().delete(fileId=file_id).execute()
                except Exception:
                    pass
                user_folder_id = drive_service.create_user_folder(str(current_user._id))
                new_file_id = drive_service.upload_file(
                    file_content=file_content_out,
                    file_name=file_name,
                    mime_type=mime_type,
                    folder_id=user_folder_id,
                )
                await db.datasets.update_one(
                    {"_id": ObjectId(dataset_id)},
                    {"$set": {"google_drive_file_id": new_file_id}},
                )
                saved = True
            except Exception:
                pass
        if not saved:
            try:
                local_storage.delete_file(file_id)
            except Exception:
                pass
            file_ext = file_name.lower().split(".")[-1] if "." in file_name else "csv"
            user_folder_path = local_storage.create_user_folder(
                str(current_user._id), dataset_type=file_ext
            )
            new_file_id = local_storage.upload_file(
                file_content=file_content_out,
                file_name=file_name,
                mime_type=mime_type,
                folder_path=user_folder_path,
            )
            await db.datasets.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$set": {"google_drive_file_id": new_file_id}},
            )
        await db.datasets.update_one(
            {"_id": ObjectId(dataset_id)},
            {"$set": {"file_size": len(file_content_out)}},
        )
        return {
            "success": True,
            "new_column_name": column_name,
            "new_column_data": new_vals,
            "message": "Column generated and saved successfully.",
            "row_count": len(df),
            "column_count": len(df.columns),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding intelligent column: {str(e)}",
        )

