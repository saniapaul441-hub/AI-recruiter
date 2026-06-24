"""
routes/auth.py
--------------
Three endpoints:

  POST /auth/register   → create a new recruiter account
  POST /auth/login      → returns a JWT token
  GET  /auth/me         → returns current logged-in user info
                          (requires valid token in Authorization header)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.utils.security import create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

# FastAPI reads the token from the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─── Dependency: get current logged-in user ───────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Reusable dependency — add to any route to protect it.
    Usage:  current_user: User = Depends(get_current_user)
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    email: str = payload.get("sub")
    if not email:
        raise credentials_error

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise credentials_error

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Stricter dependency — only admin role can access the route.
    Usage:  admin: User = Depends(require_admin)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Creates a new user account.
    Returns the user object (without password).

    Example request body:
      {
        "email": "ali@company.com",
        "password": "secret123",
        "full_name": "Ali Khan",
        "role": "recruiter"
      }
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Verifies credentials and returns a JWT token.
    The frontend stores this token and sends it with every future request.

    Example request body:
      { "email": "ali@company.com", "password": "secret123" }

    Example response:
      { "access_token": "eyJ...", "token_type": "bearer", "role": "recruiter" }
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(data={"sub": user.email, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        email=user.email,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the currently logged-in user's profile.
    Requires: Authorization: Bearer <token> header.
    """
    return current_user