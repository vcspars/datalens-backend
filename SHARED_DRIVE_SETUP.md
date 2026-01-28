# Google Drive Shared Drive Setup (REQUIRED)

## Why Shared Drive?

Service accounts **do not have storage quota** in their own Google Drive. They can only store files in **Shared Drives** (formerly Team Drives). This is a Google Workspace feature.

## Solution: Create a Shared Drive

### Option 1: Create Shared Drive Manually (Recommended)

1. **Go to Google Drive:**
   - Open [Google Drive](https://drive.google.com)
   - Make sure you're using a Google Workspace account (not personal Gmail)

2. **Create Shared Drive:**
   - Click "New" button (or the "+" icon)
   - Select "Shared drive"
   - Name it: **`DataLens Storage`** (exactly this name)
   - Click "Create"

3. **Add Service Account:**
   - Open your `backend/credentials.json` file
   - Find the `client_email` field (looks like: `xxx@xxx.iam.gserviceaccount.com`)
   - Go back to the Shared Drive you just created
   - Click "Manage members" or the people icon
   - Click "Add members"
   - Paste the service account email
   - Set role to **"Manager"** or **"Content Manager"**
   - Click "Send"

4. **Verify:**
   - The service account should now appear as a member
   - Restart your backend server
   - Try uploading a file again

### Option 2: Automatic Creation (If you have permissions)

The code will try to automatically create a Shared Drive named "DataLens Storage", but this requires:
- Your Google Cloud project to have Shared Drive creation enabled
- Service account to have proper IAM permissions

If automatic creation fails, use Option 1.

## Troubleshooting

**Error: "Service Accounts do not have storage quota"**
- ✅ Solution: Use Shared Drive (see above)

**Error: "Cannot access Shared Drive"**
- Check that the Shared Drive is named exactly "DataLens Storage"
- Verify the service account email is added as a member
- Make sure the service account has "Manager" or "Content Manager" role

**Error: "insufficientPermissions"**
- The service account needs to be added to the Shared Drive
- Check the service account email in credentials.json matches the one added to Shared Drive

## Finding Your Service Account Email

Open `backend/credentials.json` and look for:
```json
{
  "client_email": "your-service-account@your-project-id.iam.gserviceaccount.com",
  ...
}
```

This is the email you need to add to the Shared Drive.

