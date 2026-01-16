import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session, select

from app.database import init_db, get_session
from app.models import Goal, Timeline, TemporalContract, TimePrison
from app.llm_simulator import simulate_time_self
from app.temporal_engine import predict_failure, update_stability, should_lock_prison
from app.ws_manager import WSManager

from app.routes.auth import router as auth_router
from app.routes.goals import router as goals_router
from app.routes.contracts import router as contracts_router
from app.routes.timelines import router as timelines_router

app = FastAPI(title="Temporal Blackmail - Time Crime Backend")
manager = WSManager()

app.include_router(auth_router)
app.include_router(goals_router)
app.include_router(contracts_router)
app.include_router(timelines_router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"status": "Temporal Blackmail backend alive"}


@app.get("/prison/{user_id}")
def prison_state(user_id: int, session: Session = Depends(get_session)):
    prison = session.exec(select(TimePrison).where(TimePrison.user_id == user_id)).first()
    return prison


@app.websocket("/ws/time-stream/{user_id}/{timeline_id}")
async def time_stream(ws: WebSocket, user_id: int, timeline_id: int, session: Session = Depends(get_session)):
    """
    Live 3-way chat among Past/Present/Future.
    Timeline stability drops if user keeps talking without completing tasks.
    Eventually triggers TIME PRISON.
    """
    room = f"user:{user_id}:timeline:{timeline_id}"
    await manager.connect(room, ws)

    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action", "chat")
            payload = msg.get("payload", {})

            # fetch data
            goals = session.exec(select(Goal).where(Goal.user_id == user_id)).all()
            timeline = session.get(Timeline, timeline_id)
            contracts = session.exec(select(TemporalContract).where(TemporalContract.timeline_id == timeline_id)).all()

            completed = sum(1 for g in goals if g.completed)
            total = len(goals)
            ratio = completed / max(1, total)

            # prediction
            pred = predict_failure(total, ratio)

            # ✅ ignored warning logic:
            # If user sends messages while having incomplete goals => timeline destabilizes
            incomplete = total - completed
            ignored_warnings = 0

            if incomplete > 0:
                # more incomplete goals => higher ignored warnings
                ignored_warnings = min(5, 1 + incomplete // 3)

            # ✅ update stability based on behavior
            timeline.stability = update_stability(
                current=timeline.stability,
                ignored_warnings=ignored_warnings,
                completed_tasks=completed,
            )

            # prison check
            prison = session.exec(select(TimePrison).where(TimePrison.user_id == user_id)).first()
            if prison is None:
                prison = TimePrison(user_id=user_id, locked=False)

            # lock if timeline unstable + prediction says high fail chance
            if should_lock_prison(timeline.stability, pred.will_fail_probability):
                prison.locked = True
                prison.reason = "Future You has declared you a temporal liability."
                prison.unlock_condition = "Complete at least 1 goal to restore the timeline."
            else:
                # unlock automatically if at least one task completed
                if completed > 0:
                    prison.locked = False
                    prison.reason = ""
                    prison.unlock_condition = ""

            # persist
            session.add(timeline)
            session.add(prison)
            session.commit()

            # context for time-selves
            context = {
                "stability": timeline.stability,
                "unfinished_goals": incomplete,
                "open_contracts": len(contracts),
                "prediction": pred.will_fail_probability,
            }

            # memory corruption increases as stability decreases
            corruption = max(0.0, 1.0 - timeline.stability)

            # simulate time selves
            past_msg = simulate_time_self("PAST", context, corruption=corruption * 0.3)
            present_msg = simulate_time_self("PRESENT", context, corruption=corruption * 0.1)
            future_msg = simulate_time_self("FUTURE", context, corruption=corruption * 0.6)

            await manager.broadcast(room, {
                "type": "time_stream_update",
                "timeline": {
                    "id": timeline.id,
                    "name": timeline.name,
                    "stability": timeline.stability,
                    "prediction_fail_prob": pred.will_fail_probability,
                    "prediction_reason": pred.reason,
                    "ignored_warnings": ignored_warnings,
                    "incomplete_goals": incomplete,
                },
                "prison": {
                    "locked": prison.locked,
                    "reason": prison.reason,
                    "unlock_condition": prison.unlock_condition,
                },
                "selves": [
                    {"self": "PAST", "message": past_msg},
                    {"self": "PRESENT", "message": present_msg},
                    {"self": "FUTURE", "message": future_msg},
                ],
            })

    except WebSocketDisconnect:
        manager.disconnect(room, ws)
