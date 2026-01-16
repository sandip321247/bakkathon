from datetime import datetime, timedelta , timezone
from jose import jwt
from passlib.context import CryptContext

SECRET_KEY = "CHANGE_THIS_TO_REAL_SECRET"
ALGO = "HS256"
ACCESS_EXPIRE_MIN = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MIN)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)
