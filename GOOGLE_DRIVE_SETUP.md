# Google Drive Setup Instructions

To enable Google Drive storage for datasets, you need to set up Google Cloud credentials.

## Steps:

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google Drive API:**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"

3. **Create Service Account:**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Fill in the service account details
   - Click "Create and Continue"
   - Grant the service account "Editor" role (or create a custom role)
   - Click "Done"

4. **Create and Download Key:**
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Select "JSON" format
   - Download the JSON file

5. **Save Credentials:**
   - Rename the downloaded JSON file to `credentials.json`
   - Place it in the `backend/` directory
   - **Important:** Add `credentials.json` to `.gitignore` to keep it secure

6. **Create Shared Drive (REQUIRED for Service Accounts):**
   - Service accounts don't have storage quota in their own drive
   - You need to create a Shared Drive (Google Workspace feature)
   - **Option A: Create Shared Drive via API (Automatic):**
     - The code will automatically try to create a Shared Drive named "DataLens Storage"
     - Make sure your service account has permission to create shared drives
   - **Option B: Create Shared Drive Manually:**
     - Go to Google Drive
     - Click "New" > "Shared drive"
     - Name it "DataLens Storage" (or update the code to use a different name)
     - Add the service account email (from credentials.json) as a member
     - Give it "Manager" or "Content Manager" role
     - The service account email looks like: `your-service-account@your-project-id.iam.gserviceaccount.com`

7. **Alternative: Use OAuth Delegation (For Personal Accounts):**
   - If you don't have Google Workspace, you can use OAuth instead
   - This requires users to authorize the app to access their Google Drive
   - More complex but works with personal Google accounts

## Environment Variable (Optional):

You can also set the credentials file path via environment variable:
```bash
export GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json
```

## Testing:

Once set up, the backend will automatically:
- Create user-specific folders in Google Drive
- Upload files to those folders
- Store file metadata in MongoDB

## Note:

If credentials are not set up, the service will gracefully handle the absence and you can implement a fallback storage mechanism.

