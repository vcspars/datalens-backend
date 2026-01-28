# DataLens Backend API

FastAPI backend for DataLens application with MongoDB.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure MongoDB is running on `mongodb://localhost:27017`

3. Run the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables

Create a `.env` file in the `backend` directory to override default settings:

```
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=datalens_db
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## API Endpoints

### Authentication

- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user info (requires authentication)

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # MongoDB connection
│   ├── models/              # Data models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── routes/              # API routes
│   │   ├── __init__.py
│   │   └── auth.py
│   └── utils/               # Utilities
│       ├── __init__.py
│       └── security.py
├── requirements.txt
└── README.md
```

