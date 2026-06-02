"""
Live dashboard server for the Infotainment State Machine.

Start with:
    uvicorn python.server:app --reload
from the project root directory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import infotainment_sm as sm
from python import transition_logger as tl

_machine: sm.InfotainmentStateMachine = sm.InfotainmentStateMachine()
_subscribers: List[WebSocket] = []
_STATIC = Path(__file__).parent.parent / "static"


async def _broadcast(payload: dict) -> None:
    dead = []
    for ws in _subscribers:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _subscribers.remove(ws)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    tl.init_db()
    yield


app = FastAPI(title="Infotainment SM Dashboard", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


# ──────────────────────────────────────────────────────────────── routes ──── #

@app.get("/", response_class=HTMLResponse)
async def index():
    return (_STATIC / "index.html").read_text()


@app.get("/api/state")
async def get_state():
    s = _machine.get_state()
    return {"state": sm.state_name(s), "value": int(s)}


@app.get("/api/context")
async def get_context():
    ctx = _machine.get_context()
    return {
        "speed_kmh":               ctx.speed_kmh,
        "in_reverse":              ctx.in_reverse,
        "engine_running":          ctx.engine_running,
        "phone_connected":         ctx.phone_connected,
        "carplay_connected":       ctx.carplay_connected,
        "android_auto_connected":  ctx.android_auto_connected,
        "usb_connected":           ctx.usb_connected,
        "aux_connected":           ctx.aux_connected,
        "ev_plugged_in":           ctx.ev_plugged_in,
        "dab_available":           ctx.dab_available,
        "streaming_connected":     ctx.streaming_connected,
        "call_active":             ctx.call_active,
    }


@app.post("/api/context")
async def set_context(body: dict):
    ctx = _machine.get_context()
    _BOOL_FIELDS = {
        "in_reverse", "engine_running", "phone_connected",
        "carplay_connected", "android_auto_connected", "usb_connected",
        "aux_connected", "ev_plugged_in", "dab_available",
        "streaming_connected", "call_active",
    }
    for key, val in body.items():
        if key == "speed_kmh":
            ctx.speed_kmh = float(val)
        elif key in _BOOL_FIELDS:
            setattr(ctx, key, bool(val))
    _machine.set_context(ctx)
    return {"ok": True}


@app.get("/api/valid_events")
async def valid_events():
    evs = _machine.get_valid_events()
    return {"valid_events": [sm.event_name(e) for e in evs]}


@app.post("/api/event/{event_name}")
async def fire_event(event_name: str):
    try:
        event = getattr(sm.Event, event_name)
    except AttributeError:
        return JSONResponse({"error": f"Unknown event: {event_name}"}, status_code=400)

    from_state = sm.state_name(_machine.get_state())
    success    = _machine.transition(event)
    to_state   = sm.state_name(_machine.get_state())
    ctx        = _machine.get_context()

    tl.log(from_state, event_name, to_state, success, {
        "speed_kmh":  ctx.speed_kmh,
        "in_reverse": ctx.in_reverse,
    })

    payload = {
        "type":       "transition",
        "from_state": from_state,
        "event":      event_name,
        "to_state":   to_state,
        "success":    success,
    }
    await _broadcast(payload)
    return payload


@app.post("/api/reset")
async def reset():
    global _machine
    _machine = sm.InfotainmentStateMachine()
    await _broadcast({"type": "reset", "state": "BOOT"})
    return {"ok": True}


@app.get("/api/history")
async def history(limit: int = 50):
    return {"history": tl.recent(limit)}


@app.get("/api/stats")
async def stats():
    return tl.stats()


# ──────────────────────────────────────────────────────────── websocket ───── #

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    _subscribers.append(websocket)
    await websocket.send_json({
        "type":  "connected",
        "state": sm.state_name(_machine.get_state()),
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _subscribers:
            _subscribers.remove(websocket)
