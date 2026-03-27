"""Authentication routes"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.database import get_database
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse
from app.models.user import User
from app.models.chat import ChatSession
from app.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token
)
from datetime import timedelta
from app.config import settings
from bson import ObjectId

print("[AuthRoute] Router initialized")


router = APIRouter(prefix="/auth", tags=["authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def _ensure_chat_session(db, user_id: str) -> str:
    """Create a chat session for the user if one doesn't exist yet."""
    existing = await db.chat_sessions.find_one({"user_id": user_id})
    if existing:
        session_id = str(existing["_id"])
        print(f"[AuthRoute] Chat session already exists for user {user_id}: {session_id}")
        return session_id

    session = ChatSession(user_id=user_id)
    result = await db.chat_sessions.insert_one(session.to_dict())
    session_id = str(result.inserted_id)
    print(f"[AuthRoute] Created chat session for user {user_id}: {session_id}")
    return session_id


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current authenticated user"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    db = get_database()
    user_data = await db.users.find_one({"_id": ObjectId(user_id)})
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return User.from_dict(user_data)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(signup_data: SignupRequest):
    """User registration endpoint"""
    try:
        db = get_database()
        
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection not available"
            )
        
        # Validate password confirmation
        if signup_data.password != signup_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
        
        # Check if user already exists
        existing_user = await db.users.find_one({"email": signup_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        password_hash = get_password_hash(signup_data.password)
        
        # Create user with role
        user = User(
            email=signup_data.email,
            password_hash=password_hash,
            full_name=signup_data.full_name,
            role=signup_data.role,
        )
        
        # Insert user into database
        result = await db.users.insert_one(user.to_dict())
        
        # Create access token (include role)
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(result.inserted_id), "email": user.email, "role": user.role},
            expires_delta=access_token_expires
        )

        # Auto-create chat session for new user
        await _ensure_chat_session(db, str(result.inserted_id))
        print(f"[AuthRoute] Signup complete for {user.email} | role={user.role}")

        return TokenResponse(access_token=access_token, token_type="bearer")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during signup: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest):
    """User login endpoint"""
    db = get_database()
    
    # Find user by email
    user_data = await db.users.find_one({"email": login_data.email})
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    user = User.from_dict(user_data)
    
    # Verify password
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token (include role)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user._id), "email": user.email, "role": user.role},
        expires_delta=access_token_expires
    )

    # Ensure chat session exists for this user
    db = get_database()
    await _ensure_chat_session(db, str(user._id))
    print(f"[AuthRoute] Login complete for {user.email} | role={user.role}")

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user._id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
    )
