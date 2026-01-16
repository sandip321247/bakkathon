from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import Goal, User
from app.schemas import GoalCreate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("/{user_id}")
def create_goal(user_id: int, payload: GoalCreate, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")

    goal = Goal(user_id=user_id, title=payload.title, description=payload.description, due_date=payload.due_date)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.get("/{user_id}")
def list_goals(user_id: int, session: Session = Depends(get_session)):
    goals = session.exec(select(Goal).where(Goal.user_id == user_id)).all()
    return goals


@router.patch("/{goal_id}/complete")
def complete_goal(goal_id: int, session: Session = Depends(get_session)):
    goal = session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(404, "goal not found")
    goal.completed = True
    session.add(goal)
    session.commit()
    return {"status": "completed"}
