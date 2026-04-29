"""Security utilities for password hashing and JWT tokens"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    # Bcrypt has a 72-byte limit, truncate by bytes if necessary
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to 72 bytes and decode back to string
        truncated_bytes = password_bytes[:72]
        # Find the last valid UTF-8 character boundary
        while truncated_bytes and truncated_bytes[-1] & 0xC0 == 0x80:
            truncated_bytes = truncated_bytes[:-1]
        password_bytes = truncated_bytes
    
    # Use bcrypt directly to verify
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password - ensures password is within bcrypt's 72-byte limit"""
    # Ensure password is a string
    if not isinstance(password, str):
        password = str(password)
    
    # Convert to bytes to check actual byte length
    password_bytes = password.encode('utf-8')
    byte_length = len(password_bytes)
    
    # Bcrypt has a strict 72-byte limit - truncate if necessary
    if byte_length > 72:
        # Truncate to exactly 72 bytes
        password_bytes = password_bytes[:72]
        # Remove any incomplete UTF-8 sequences at the end
        # UTF-8 continuation bytes have pattern 10xxxxxx (0x80-0xBF)
        while len(password_bytes) > 0 and (password_bytes[-1] & 0xC0) == 0x80:
            password_bytes = password_bytes[:-1]
        # Decode back to string
        password = password_bytes.decode('utf-8', errors='ignore')
    
    # Final safety check - ensure it's definitely <= 72 bytes
    final_check = password.encode('utf-8')
    if len(final_check) > 72:
        # Last resort: force truncate character by character
        while len(password.encode('utf-8')) > 72 and len(password) > 0:
            password = password[:-1]
    
    # Verify one more time before hashing
    final_bytes = password.encode('utf-8')
    if len(final_bytes) > 72:
        raise ValueError(f"Password cannot be truncated to <= 72 bytes. Final length: {len(final_bytes)} bytes")
    
    # Hash the password using bcrypt directly
    salt = bcrypt.gensalt(rounds=12)
    password_bytes_for_hashing = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes_for_hashing, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

