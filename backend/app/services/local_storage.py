"""Local file storage service as fallback when Google Drive is not available"""
import os
from pathlib import Path
from datetime import datetime
import uuid


class LocalStorageService:
    """Service for storing files locally"""
    
    def __init__(self):
        # Create storage directory if it doesn't exist
        # Changed from "backend/storage" to "datasets"
        self.storage_dir = Path("datasets")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def create_user_folder(self, user_id: str, dataset_type: str = None) -> str:
        """Create a folder for a user in local storage, optionally organized by dataset type"""
        user_folder = self.storage_dir / f"user_{user_id}"
        user_folder.mkdir(parents=True, exist_ok=True)
        
        # If dataset type is provided, create a subfolder for that type
        if dataset_type:
            # Normalize dataset type (csv, pdf, xls, xlsx -> csv, pdf, xls)
            if dataset_type.lower() in ['xlsx', 'xls']:
                type_folder = user_folder / "xls"
            elif dataset_type.lower() == 'pdf':
                type_folder = user_folder / "pdf"
            elif dataset_type.lower() == 'csv':
                type_folder = user_folder / "csv"
            else:
                # Default to a generic folder if type is unknown
                type_folder = user_folder / dataset_type.lower()
            
            type_folder.mkdir(parents=True, exist_ok=True)
            return str(type_folder)
        
        return str(user_folder)
    
    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
        folder_path: str
    ) -> str:
        """Upload a file to local storage"""
        folder = Path(folder_path)
        # Generate unique filename to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        file_stem = Path(file_name).stem
        file_ext = Path(file_name).suffix
        unique_filename = f"{file_stem}_{unique_id}{file_ext}"
        
        file_path = folder / unique_filename
        file_path.write_bytes(file_content)
        
        # Return the relative path as the "file_id"
        return str(file_path.relative_to(self.storage_dir))
    
    def download_file(self, file_id: str) -> bytes:
        """Download a file from local storage"""
        file_path = self.storage_dir / file_id
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_id}")
        return file_path.read_bytes()
    
    def delete_file(self, file_id: str) -> None:
        """Delete a file from local storage"""
        file_path = self.storage_dir / file_id
        if file_path.exists():
            file_path.unlink()
    
    def get_file_url(self, file_id: str) -> str:
        """Get a local file path"""
        return str(self.storage_dir / file_id)


# Global instance
local_storage = LocalStorageService()
