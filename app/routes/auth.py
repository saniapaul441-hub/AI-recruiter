from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.auth import User
from app.schemas.auth import UserRegister, UserLogin, Token
from app.utils.security import get_password_hash, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user

def require_role(allowed_roles: list[str]):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for your role"
            )
        return current_user
    return dependency

# Helper dependencies
require_recruiter = require_role(["recruiter", "admin"])
require_admin = require_role(["admin"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check if email exists
    db_user = db.query(User).filter(User.email == user_in.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate role
    role = user_in.role
    if role not in ["recruiter", "admin"]:
        role = "recruiter"
        
    hashed_pwd = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        password_hash=hashed_pwd,
        role=role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(subject=new_user.email, role=new_user.role)
    return Token(access_token=access_token, token_type="bearer", role=new_user.role)

@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.email, role=user.role)
    return Token(access_token=access_token, token_type="bearer", role=user.role)

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role
    }

from app.schemas.auth import SMTPSettingsUpdate, SMTPSettingsResponse
from app.services.automation import send_smtp_email

@router.get("/smtp", response_model=SMTPSettingsResponse)
def get_smtp_settings(current_user: User = Depends(require_recruiter)):
    """Retrieve the current recruiter's SMTP settings (password hidden)."""
    return SMTPSettingsResponse(
        smtp_host=current_user.smtp_host,
        smtp_port=current_user.smtp_port or 587,
        smtp_username=current_user.smtp_username,
        smtp_from=current_user.smtp_from
    )

@router.put("/smtp", response_model=SMTPSettingsResponse)
def update_smtp_settings(
    settings_in: SMTPSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Update the recruiter's SMTP settings."""
    if settings_in.smtp_host is not None:
        current_user.smtp_host = settings_in.smtp_host.strip() if settings_in.smtp_host else None
    if settings_in.smtp_port is not None:
        current_user.smtp_port = settings_in.smtp_port
    if settings_in.smtp_username is not None:
        current_user.smtp_username = settings_in.smtp_username.strip() if settings_in.smtp_username else None
    if settings_in.smtp_password is not None:
        current_user.smtp_password = settings_in.smtp_password.strip() if settings_in.smtp_password else None
    if settings_in.smtp_from is not None:
        current_user.smtp_from = settings_in.smtp_from.strip() if settings_in.smtp_from else None
        
    db.commit()
    db.refresh(current_user)
    return SMTPSettingsResponse(
        smtp_host=current_user.smtp_host,
        smtp_port=current_user.smtp_port or 587,
        smtp_username=current_user.smtp_username,
        smtp_from=current_user.smtp_from
    )

@router.post("/smtp/test")
def test_smtp_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter)
):
    """Send a test email using the recruiter's credentials to verify settings."""
    if not current_user.smtp_host or not current_user.smtp_username or not current_user.smtp_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP is not fully configured for your account. Please set Host, Username, and Password."
        )
        
    recipient = current_user.smtp_username or current_user.email
    
    subject = "AI Recruiter - SMTP Integration Test"
    body = (
        f"Hi,\n\n"
        f"Congratulations! Your dynamic SMTP credentials have been successfully connected to the AI Recruiter platform.\n\n"
        f"Outreach and feedback emails for candidates in your workspaces will now be sent directly from this email account.\n\n"
        f"Best regards,\n"
        f"AI Recruiter System Verification Service"
    )
    
    success = send_smtp_email(recipient, subject, body, config_user=current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email. Please check your SMTP settings, username, and App Password."
        )
        
    return {"status": "success", "message": f"Test email successfully sent to {recipient}."}

