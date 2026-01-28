# How to Start the Backend Server

## Step 1: Make sure MongoDB is running

The backend requires MongoDB to be running on `mongodb://localhost:27017`

**On Windows:**
- If MongoDB is installed as a service, it should be running automatically
- To check if MongoDB is running, open Command Prompt and run:
  ```
  net start MongoDB
  ```
- If it's not installed, download from: https://www.mongodb.com/try/download/community

**To verify MongoDB is running:**
- Open a new terminal and run:
  ```
  mongosh
  ```
- If it connects, MongoDB is running. Type `exit` to quit.

## Step 2: Start the Backend Server

Open a terminal/command prompt and run:

```bash
cd backend
python run.py
```

Or alternatively:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Started server process
INFO:     Waiting for application startup.
Connected to MongoDB: mongodb://localhost:27017
Database: datalens_db
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## Step 3: Verify the Server is Running

Open your browser and go to:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

If you see the API documentation or `{"status": "healthy"}`, the server is running correctly!

## Troubleshooting

**If you get "Connection refused" error:**
1. Make sure the backend server is running (Step 2)
2. Make sure MongoDB is running (Step 1)
3. Check that port 8000 is not being used by another application

**If you get MongoDB connection error:**
1. Make sure MongoDB is installed and running
2. Verify the connection string in `backend/app/config.py` matches your MongoDB setup
3. Try connecting with `mongosh` to verify MongoDB is accessible

