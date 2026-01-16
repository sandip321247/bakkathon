from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Timeline, TimePrison
from app.schemas import RegisterRequest, TokenResponse
from app.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    """
    Safe register:
    - Validates password length for bcrypt (<=72 bytes)
    - Prevents duplicate username crash
    - Creates initial timeline + prison state
    """

    # ✅ bcrypt safety validation
    try:
        hashed = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = User(username=payload.username, hashed_password=hashed)
    session.add(user)

    try:
        session.commit()
        session.refresh(user)

    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="username already exists")

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"register failed: {str(e)}")

    # init timeline + prison state
    timeline = Timeline(user_id=user.id, name="prime", stability=1.0)
    prison = TimePrison(user_id=user.id, locked=False)

    session.add(timeline)
    session.add(prison)
    session.commit()

    return TokenResponse(access_token=create_access_token(user.username))


@router.post("/login", response_model=TokenResponse)
def login(payload: RegisterRequest, session: Session = Depends(get_session)):
    """
    Login:
    - Validates bcrypt safety
    - Returns JWT token
    """
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")

    try:
        ok = verify_password(payload.password, user.hashed_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(status_code=401, detail="invalid credentials")

    return TokenResponse(access_token=create_access_token(user.username))
