import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import TemporalContract, Timeline, User
from app.schemas import ContractCreate

router = APIRouter(prefix="/contracts", tags=["contracts"])


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@router.post("/{user_id}/{timeline_id}")
def make_contract(user_id: int, timeline_id: int, payload: ContractCreate, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    timeline = session.get(Timeline, timeline_id)
    if not user or not timeline:
        raise HTTPException(404, "invalid user/timeline")

    last = session.exec(
        select(TemporalContract)
        .where(TemporalContract.timeline_id == timeline_id)
        .order_by(TemporalContract.id.desc())
    ).first()

    prev_hash = last.contract_hash if last else ""
    raw = f"{prev_hash}|{user_id}|{timeline_id}|{payload.contract_text}"
    contract_hash = compute_hash(raw)

    contract = TemporalContract(
        user_id=user_id,
        timeline_id=timeline_id,
        contract_text=payload.contract_text,
        prev_hash=prev_hash,
        contract_hash=contract_hash,
    )
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


@router.get("/{timeline_id}")
def list_contracts(timeline_id: int, session: Session = Depends(get_session)):
    return session.exec(select(TemporalContract).where(TemporalContract.timeline_id == timeline_id)).all()
