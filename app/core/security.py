from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models.user import User

# Used to extract token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# 🔐 Create JWT Access Token
def create_access_token(data: dict):
    to_encode = data.copy()
    # expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# 👤 Extract User from Token
from jose import JWTError, jwt
import logging

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
import logging

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        logging.info("JWT Payload: %s", payload)
        user_email: str = payload.get("sub")

        if user_email is None:
            logging.warning("JWT token missing 'sub' claim")
            raise credentials_exception

    except JWTError as e:
        logging.error("JWT decode failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token is invalid: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == user_email).first()
    if user is None:
        logging.warning("User not found in DB for email: %s", user_email)
        raise credentials_exception

    return user

