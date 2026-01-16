from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Timeline
from app.schemas import TimelineForkRequest

router = APIRouter(prefix="/timelines", tags=["timelines"])


@router.get("/{user_id}")
def list_timelines(user_id: int, session: Session = Depends(get_session)):
    """
    ✅ Correct SQLModel query:
    session.exec(select(Timeline).where(...)).all()
    """
    timelines = session.exec(select(Timeline).where(Timeline.user_id == user_id)).all()
    return timelines


@router.post("/{timeline_id}/fork")
def fork_timeline(timeline_id: int, payload: TimelineForkRequest, session: Session = Depends(get_session)):
    base = session.get(Timeline, timeline_id)
    if not base:
        raise HTTPException(404, "timeline not found")

    forked = Timeline(
        user_id=base.user_id,
        parent_timeline_id=base.id,
        name=payload.new_name,
        stability=base.stability * 0.9,
    )
    session.add(forked)
    session.commit()
    session.refresh(forked)
    return forked
