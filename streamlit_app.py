import json
import threading
import time
from queue import Queue, Empty
from typing import Any

import requests
import streamlit as st
from websocket import WebSocketApp
from streamlit_autorefresh import st_autorefresh


# ============================================================
# CONFIG
# ============================================================
API_BASE = "http://127.0.0.1:8000"


# ============================================================
# API WRAPPERS
# ============================================================
def api_get(path: str) -> Any:
    r = requests.get(f"{API_BASE}{path}", timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()


def api_post(path: str, payload: dict) -> Any:
    r = requests.post(f"{API_BASE}{path}", json=payload, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()


def api_patch(path: str) -> Any:
    r = requests.patch(f"{API_BASE}{path}", timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()


# ✅ CACHED GET (reduces backend spam)
@st.cache_data(ttl=3)
def cached_get(path: str):
    return api_get(path)


# ============================================================
# SESSION STATE INIT
# ============================================================
def init_state():
    defaults = {
        "token": None,
        "user_id": 1,
        "timeline_id": 1,

        # WS runtime
        "ws_running": False,
        "ws_connected": False,
        "ws_inbox": Queue(),   # WS -> UI
        "ws_outbox": Queue(),  # UI -> WS
        "ws_stop_event": None,
        "ws_thread": None,

        # app state
        "timelines": [],
        "timeline_state": {},
        "prison_state": {},
        "time_stream": [],
        "last_ws_message_ts": 0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ============================================================
# THREAD-SAFE WEBSOCKET WORKER (NO session_state inside)
# ============================================================
def ws_worker(user_id: int, timeline_id: int, inbox: Queue, outbox: Queue, stop_event: threading.Event):
    ws_url = f"ws://127.0.0.1:8000/ws/time-stream/{user_id}/{timeline_id}"

    def on_open(ws):
        inbox.put({"type": "_status", "connected": True})

    def on_message(ws, message: str):
        try:
            data = json.loads(message)
            inbox.put(data)
        except Exception:
            pass

    def on_close(ws, code, msg):
        inbox.put({"type": "_status", "connected": False})

    def on_error(ws, error):
        inbox.put({"type": "_status", "connected": False, "error": str(error)})

    ws_app = WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error,
    )

    # internal ws thread
    def run_ws():
        ws_app.run_forever()

    t = threading.Thread(target=run_ws, daemon=True)
    t.start()

    # send loop
    while not stop_event.is_set():
        try:
            item = outbox.get(timeout=0.2)
            ws_app.send(json.dumps(item))
        except Empty:
            continue
        except Exception:
            time.sleep(0.2)

    try:
        ws_app.close()
    except Exception:
        pass


def ensure_ws_running():
    if st.session_state.ws_running:
        return

    st.session_state.ws_running = True
    st.session_state.ws_stop_event = threading.Event()

    thread = threading.Thread(
        target=ws_worker,
        args=(
            st.session_state.user_id,
            st.session_state.timeline_id,
            st.session_state.ws_inbox,
            st.session_state.ws_outbox,
            st.session_state.ws_stop_event,
        ),
        daemon=True,
    )
    thread.start()
    st.session_state.ws_thread = thread


def restart_ws():
    if st.session_state.ws_running and st.session_state.ws_stop_event:
        st.session_state.ws_stop_event.set()

    st.session_state.ws_running = False
    st.session_state.ws_connected = False

    # reset queues (avoid old timeline data)
    st.session_state.ws_inbox = Queue()
    st.session_state.ws_outbox = Queue()

    ensure_ws_running()


def consume_ws_messages() -> None:
    inbox: Queue = st.session_state.ws_inbox

    while True:
        try:
            msg = inbox.get_nowait()
        except Empty:
            break

        if msg.get("type") == "_status":
            st.session_state.ws_connected = bool(msg.get("connected"))
            continue

        if msg.get("type") == "time_stream_update":
            st.session_state.timeline_state = msg.get("timeline", {})
            st.session_state.prison_state = msg.get("prison", {})
            st.session_state.time_stream = msg.get("selves", [])
            st.session_state.last_ws_message_ts = time.time()


# ============================================================
# HELPERS
# ============================================================
def stability_color(stability: float) -> str:
    if stability >= 0.75:
        return "🟢"
    if stability >= 0.40:
        return "🟡"
    return "🔴"


def failprob_color(p: float) -> str:
    if p <= 0.30:
        return "🟢"
    if p <= 0.60:
        return "🟡"
    return "🔴"


# ============================================================
# APP START
# ============================================================
st.set_page_config(page_title="Temporal Blackmail Dashboard", layout="wide")
init_state()

# ✅ Safe refresh every 1.5s
st_autorefresh(interval=1500, key="temporal_refresh")

# WS start
ensure_ws_running()
consume_ws_messages()

st.title("⏳ Temporal Blackmail — Streamlit War Room")


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("🧬 Identity")

    tab1, tab2 = st.tabs(["Register", "Login"])
    with tab1:
        u = st.text_input("username", key="reg_user")
        p = st.text_input("password", type="password", key="reg_pass")
        if st.button("Register"):
            try:
                out = api_post("/auth/register", {"username": u, "password": p})
                st.success("Registered ✅")
                st.session_state.token = out["access_token"]

                # refresh timelines cache
                cached_get.clear()
                st.session_state.timelines = cached_get(f"/timelines/{st.session_state.user_id}")

            except Exception as e:
                st.error(str(e))

    with tab2:
        u2 = st.text_input("username ", key="login_user")
        p2 = st.text_input("password ", type="password", key="login_pass")
        if st.button("Login"):
            try:
                out = api_post("/auth/login", {"username": u2, "password": p2})
                st.success("Logged in ✅")
                st.session_state.token = out["access_token"]
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.header("👤 Demo Setup")

    st.session_state.user_id = st.number_input("user_id", min_value=1, value=int(st.session_state.user_id), step=1)

    if st.button("Refresh timelines"):
        try:
            cached_get.clear()
            st.session_state.timelines = cached_get(f"/timelines/{st.session_state.user_id}")
        except Exception as e:
            st.error(str(e))

    if not st.session_state.timelines:
        try:
            st.session_state.timelines = cached_get(f"/timelines/{st.session_state.user_id}")
        except Exception:
            st.session_state.timelines = []

    timelines = st.session_state.timelines
    timeline_map = {f"{t['id']} — {t['name']} (stability {t['stability']:.2f})": t["id"] for t in timelines} if timelines else {}

    if timeline_map:
        chosen = st.selectbox("Timeline", list(timeline_map.keys()))
        picked_id = timeline_map[chosen]

        if picked_id != st.session_state.timeline_id:
            st.session_state.timeline_id = picked_id
            restart_ws()
            st.rerun()
    else:
        st.warning("No timelines found. Register at least one user first.")

    st.divider()
    st.caption(f"WS: {'✅ connected' if st.session_state.ws_connected else '⚠️ disconnected'}")


# ============================================================
# MAIN LAYOUT
# ============================================================
left, right = st.columns([0.62, 0.38], gap="large")


# ------------------------------------------------------------
# LEFT: TIME STREAM
# ------------------------------------------------------------
with left:
    st.subheader("🕳️ Time Stream — Past / Present / Future")

    prison = st.session_state.prison_state or {}
    if prison.get("locked"):
        st.error(f"🔒 TIME PRISON ACTIVE: {prison.get('reason')}")
        st.warning(f"Unlock condition: {prison.get('unlock_condition')}")

    timeline_state = st.session_state.timeline_state or {}
    stability = float(timeline_state.get("stability", 0.0) or 0.0)
    fail_prob = float(timeline_state.get("prediction_fail_prob", 0.0) or 0.0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Timeline", timeline_state.get("name", "unknown"))
    c2.metric(f"{stability_color(stability)} Stability", f"{stability:.2f}")
    c3.metric(f"{failprob_color(fail_prob)} Failure Probability", f"{fail_prob:.2f}")

    st.caption(f"Prediction Reason: {timeline_state.get('prediction_reason', '-')}")
    st.divider()

    selves = st.session_state.time_stream or []
    if not selves:
        st.info("No messages yet. Send a message to trigger time-stream update.")
    else:
        for block in selves:
            who = block.get("self", "?")
            message = block.get("message", "")
            if who == "PAST":
                st.markdown("### 🕯️ Past You")
                st.info(message)
            elif who == "PRESENT":
                st.markdown("### 🧍 Present You")
                st.warning(message)
            else:
                st.markdown("### 🧿 Future You")
                st.error(message)

    st.divider()

    user_text = st.text_input("Speak into the timeline", placeholder="I swear I’ll do it today…")
    if st.button("Send"):
        st.session_state.ws_outbox.put({"action": "chat", "payload": {"text": user_text}})
        st.toast("Message sent into time-stream")


# ------------------------------------------------------------
# RIGHT: GOALS + CONTRACTS
# ------------------------------------------------------------
with right:
    st.subheader("📌 Goals")

    try:
        goals = cached_get(f"/goals/{st.session_state.user_id}")
    except Exception:
        goals = []

    if goals:
        for g in goals:
            done = "✅" if g["completed"] else "⬜"
            st.markdown(f"**{done} {g['title']}**")
            st.caption(g.get("description", ""))

            if not g["completed"]:
                if st.button(f"Complete #{g['id']}", key=f"complete_{g['id']}"):
                    try:
                        api_patch(f"/goals/{g['id']}/complete")
                        cached_get.clear()
                        st.success("Goal completed ✅")
                        st.session_state.ws_outbox.put({"action": "chat", "payload": {"text": "Task completed"}})
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            st.divider()
    else:
        st.info("No goals yet. Create one below.")

    with st.expander("➕ Create Goal", expanded=True):
        title = st.text_input("Title", key="goal_title")
        desc = st.text_area("Description", key="goal_desc")
        if st.button("Create Goal"):
            try:
                api_post(f"/goals/{st.session_state.user_id}", {"title": title, "description": desc})
                cached_get.clear()
                st.success("Created ✅")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("📜 Temporal Contracts")

    try:
        contracts = cached_get(f"/contracts/{st.session_state.timeline_id}")
    except Exception:
        contracts = []

    if contracts:
        for c in contracts[::-1]:
            st.markdown(f"**Contract #{c['id']}**")
            st.code(c["contract_text"])
            st.caption(f"prev: {c['prev_hash'][:10]}...  hash: {c['contract_hash'][:10]}...")
            st.divider()
    else:
        st.info("No contracts yet.")

    with st.expander("✍️ Make Contract"):
        text = st.text_area("Contract text", placeholder="If I fail, I delete Instagram for 30 days.")
        if st.button("Seal Contract"):
            try:
                api_post(
                    f"/contracts/{st.session_state.user_id}/{st.session_state.timeline_id}",
                    {"contract_text": text},
                )
                cached_get.clear()
                st.success("Contract sealed 🧾")
                st.session_state.ws_outbox.put({"action": "chat", "payload": {"text": "Contract sealed"}})
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.subheader("🔒 Time Prison Status")

    try:
        prison_live = cached_get(f"/prison/{st.session_state.user_id}")
        if prison_live.get("locked"):
            st.error("TIME PRISON ACTIVE")
            st.write(prison_live.get("reason", ""))
            st.warning(prison_live.get("unlock_condition", ""))
        else:
            st.success("You are free (for now).")
    except Exception as e:
        st.error(str(e))
