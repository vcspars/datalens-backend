# Verify Google Drive Credentials Setup

## Quick Check:

1. **File Location:**
   - The file should be named exactly: `credentials.json` (not `credentails.json` or any other variation)
   - It should be in the `backend/` folder (same level as `app/`, `requirements.txt`, etc.)

2. **File Format:**
   - It must be a valid JSON file
   - It should start with `{` and contain fields like:
     - `"type": "service_account"`
     - `"project_id": "..."`
     - `"private_key": "-----BEGIN PRIVATE KEY-----..."`
     - `"client_email": "...@....iam.gserviceaccount.com"`

3. **To Verify:**
   - Open `backend/credentials.json` in a text editor
   - Make sure it's valid JSON (you can test at jsonlint.com)
   - Make sure it's a **Service Account** JSON (not OAuth client credentials)

## Common Issues:

- **File not found:** Make sure the file is in `backend/credentials.json`
- **Invalid JSON:** Check for syntax errors
- **Wrong type:** Must be service account, not OAuth client
- **Missing permissions:** Service account needs Google Drive API access

## Test the Setup:

After placing the file, restart your backend server and look for:
- `✓ Google Drive service initialized successfully` (good!)
- `ERROR: Google Drive credentials file not found!` (file missing or wrong location)
- `ERROR: Could not initialize Google Drive service: ...` (file format issue)

