"""Google Drive service for file storage"""
import os
import uuid
from io import BytesIO
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from app.config import settings


class GoogleDriveService:
    """Service for interacting with Google Drive API"""
    
    def __init__(self):
        self.service = None
        self.base_folder_id = None  # Folder ID in My Drive
        self.service_account_email = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Drive service"""
        try:
            # Try to find credentials.json in multiple locations
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(current_dir))
            
            possible_paths = [
                os.getenv("GOOGLE_CREDENTIALS_FILE"),
                os.path.join(backend_dir, "credentials.json"),
                "credentials.json",
                os.path.join(os.getcwd(), "credentials.json"),
            ]
            
            creds_file = None
            for path in possible_paths:
                if path and os.path.exists(path):
                    creds_file = os.path.abspath(path)
                    break
            
            if not creds_file:
                print("=" * 60)
                print("ERROR: Google Drive credentials file not found!")
                print("=" * 60)
                print("Please place credentials.json in the backend/ folder.")
                print(f"Expected location: {os.path.join(backend_dir, 'credentials.json')}")
                print("Searched locations:")
                for path in possible_paths:
                    if path:
                        print(f"  - {path}")
                print("=" * 60)
                self.service = None
                return
            
            print(f"Loading Google Drive credentials from: {creds_file}")
            
            # Load credentials from file
            from google.oauth2 import service_account
            import json
            
            # Load credentials to get service account email
            with open(creds_file, 'r') as f:
                creds_data = json.load(f)
                self.service_account_email = creds_data.get('client_email', 'unknown')
            
            creds = service_account.Credentials.from_service_account_file(
                creds_file,
                scopes=[
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/drive.file'
                ]
            )
            
            self.service = build('drive', 'v3', credentials=creds)
            print("✓ Google Drive service initialized successfully")
            print(f"  Service Account: {self.service_account_email}")
            
            # Try to get or create base folder
            try:
                self.base_folder_id = self._get_or_create_base_folder()
                print(f"✓ Using base folder ID: {self.base_folder_id}")
            except Exception as e:
                print(f"Warning: Could not access base folder: {e}")
                print("Files will be stored locally as fallback.")
                self.base_folder_id = None
        except Exception as e:
            print(f"ERROR: Could not initialize Google Drive service: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            self.service = None
    
    def _get_or_create_base_folder(self) -> str:
        """Get or create a base folder in My Drive (or shared folder)"""
        # Try to find an existing folder that's shared with the service account
        folder_names = ['Datalesnse', 'DataLens Storage', 'DataLens', 'datalens']
        
        for folder_name in folder_names:
            try:
                # Search for folders - include shared folders
                # Use 'sharedWithMe=true' to find folders shared with the service account
                query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.service.files().list(
                    q=query,
                    fields="files(id, name, parents, shared)",
                    pageSize=10,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True
                ).execute()
                items = results.get('files', [])
                
                if items:
                    # Use the first matching folder
                    folder_id = items[0]['id']
                    folder_info = items[0]
                    print(f"Found folder: {folder_name} (ID: {folder_id})")
                    print(f"  - Shared: {folder_info.get('shared', False)}")
                    print(f"  - Parents: {folder_info.get('parents', [])}")
                    return folder_id
            except Exception as e:
                print(f"Error searching for folder {folder_name}: {e}")
                continue
        
        # If no folder found, try to create one in root
        # Note: This will only work if the service account has permission
        try:
            folder_metadata = {
                'name': 'DataLens Storage',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')
            print(f"Created new folder: DataLens Storage (ID: {folder_id})")
            return folder_id
        except HttpError as error:
            error_msg = str(error)
            if 'storageQuotaExceeded' in error_msg or 'quota' in error_msg.lower():
                raise Exception(
                    f"Service account cannot create folders in My Drive due to storage quota.\n\n"
                    f"SOLUTION: Share a folder with your service account:\n"
                    f"1. Create a folder in your Google Drive (or use existing 'Datalesnse' folder)\n"
                    f"2. Right-click the folder > 'Share'\n"
                    f"3. Add this email: {self.service_account_email}\n"
                    f"4. Give 'Editor' or 'Manager' permissions\n"
                    f"5. Restart your backend server\n\n"
                    f"The folder name should be one of: Datalesnse, DataLens Storage, DataLens, or datalens"
                )
            raise Exception(f"Cannot create base folder: {error}")
    
    def create_user_folder(self, user_id: str) -> str:
        """Create a folder for a user in the base folder"""
        if not self.service:
            raise Exception("Google Drive service not initialized")
        
        # Ensure we have a base folder
        if not self.base_folder_id:
            try:
                self.base_folder_id = self._get_or_create_base_folder()
            except Exception as e:
                raise e
        
        try:
            # Check if user folder already exists
            query = f"name='user_{user_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false and '{self.base_folder_id}' in parents"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            ).execute()
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            
            # Create new folder inside base folder
            folder_metadata = {
                'name': f'user_{user_id}',
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.base_folder_id]
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            folder_id = folder.get('id')
            print(f"[DRIVE] Created user folder: user_{user_id} (ID: {folder_id})")
            return folder_id
        except HttpError as error:
            error_details = error.error_details if hasattr(error, 'error_details') else str(error)
            raise Exception(f"Error creating user folder: {error_details}")
    
    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
        folder_id: str
    ) -> str:
        """Upload a file to Google Drive"""
        if not self.service:
            raise Exception("Google Drive service not initialized")
        
        try:
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            media = MediaIoBaseUpload(
                BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            
            file_id = file.get('id')
            
            # Make the file visible to the folder owner by ensuring proper permissions
            # This helps files uploaded by service accounts be visible in shared folders
            try:
                # Get the file to check its permissions
                file_info = self.service.files().get(
                    fileId=file_id,
                    fields='id,name,parents,owners,shared'
                ).execute()
                
                # If file is not shared, we can't share it directly without user's email
                # But the file should be visible in the shared folder
                print(f"[DRIVE] File uploaded: {file_info.get('name')} (ID: {file_id})")
                print(f"[DRIVE] File parents: {file_info.get('parents')}")
                print(f"[DRIVE] File shared: {file_info.get('shared', False)}")
            except Exception as e:
                print(f"[DRIVE] Could not get file info: {e}")
            
            return file_id
        except HttpError as error:
            error_msg = str(error)
            if 'storageQuotaExceeded' in error_msg or 'quota' in error_msg.lower():
                raise Exception(
                    f"Storage quota exceeded. Service accounts cannot store files in My Drive.\n\n"
                    f"SOLUTION: Share a folder with your service account:\n"
                    f"1. Create a folder in your Google Drive\n"
                    f"2. Right-click > 'Share'\n"
                    f"3. Add: {self.service_account_email}\n"
                    f"4. Give 'Editor' permissions\n"
                    f"5. The folder will be used for storage"
                )
            raise Exception(f"Error uploading file: {error}")
    
    def download_file(self, file_id: str) -> bytes:
        """Download a file from Google Drive"""
        if not self.service:
            raise Exception("Google Drive service not initialized")
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            return file_content.getvalue()
        except HttpError as error:
            raise Exception(f"Error downloading file: {error}")
    
    def delete_file(self, file_id: str) -> None:
        """Delete a file from Google Drive"""
        if not self.service:
            raise Exception("Google Drive service not initialized")
        
        try:
            self.service.files().delete(fileId=file_id).execute()
        except HttpError as error:
            raise Exception(f"Error deleting file: {error}")
    
    def get_file_url(self, file_id: str) -> str:
        """Get a shareable URL for a file"""
        return f"https://drive.google.com/file/d/{file_id}/view"


# Global instance
drive_service = GoogleDriveService()
