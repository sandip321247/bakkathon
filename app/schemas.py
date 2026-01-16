from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[datetime] = None


class ContractCreate(BaseModel):
    contract_text: str


class TimelineForkRequest(BaseModel):
    new_name: str
