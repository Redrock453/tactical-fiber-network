"""
TFN SpiderLink C2 Server — FastAPI backend for ISR Command & Control.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import json
import time
import uuid
import math
import random
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

app = FastAPI(title="TFN SpiderLink C2", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_lock = threading.Lock()
_events: list[dict] = []
_tracks: dict[str, dict] = {}
_strike_requests: list[dict] = []
_network_nodes: dict[str, dict] = {}
_network_links: list[dict] = []
_stats = {
    "start_time": datetime.now(timezone.utc).isoformat(),
    "events_processed": 0,
    "events_rejected_duplicate": 0,
    "events_rejected_noise": 0,
    "strike_requests": 0,
    "ws_connections": 0,
    "ws_messages_sent": 0,
}
_ws_clients: list[WebSocket] = []
_seen_event_ids: set[str] = set()
_threat_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _gen_event_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:4]
    return f"evt_{ts}_{short}"


def _is_duplicate(event: dict) -> bool:
    eid = event.get("event_id", "")
    if eid in _seen_event_ids:
        return True
    src = event.get("source_node")
    seg = event.get("segment_id")
    pos = event.get("position_m", 0.0)
    ttl = event.get("target_type")
    for e in _events[-200:]:
        if (
            e.get("source_node") == src
            and e.get("segment_id") == seg
            and abs(e.get("position_m", 0.0) - pos) < 10.0
            and e.get("target_type") == ttl
        ):
            age = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            ).total_seconds()
            if age < 30:
                return True
    return False


def _is_noise(event: dict) -> bool:
    conf = event.get("classification_confidence", 0.0)
    snr = event.get("snr_db", 0.0)
    if conf < 0.15 and snr < 3.0:
        return True
    features = event.get("features", {})
    if (
        features.get("rms", 1.0) < 0.01
        and features.get("rhythm_score", 0.0) < 0.02
    ):
        return True
    return False


def _update_track(event: dict):
    tid = event.get("track_id")
    if not tid:
        return
    now = time.time()
    with _lock:
        if tid not in _tracks:
            _tracks[tid] = {
                "track_id": tid,
                "target_type": event.get("target_type", "unknown"),
                "first_seen": event["timestamp"],
                "last_seen": event["timestamp"],
                "segments": [],
                "positions": [],
                "heading": None,
                "speed_mps": None,
                "event_count": 0,
                "max_threat": event.get("threat_level", "low"),
                "active": True,
            }
        trk = _tracks[tid]
        trk["last_seen"] = event["timestamp"]
        trk["event_count"] += 1
        seg = event.get("segment_id")
        if seg and seg not in trk["segments"]:
            trk["segments"].append(seg)
        pos = event.get("position_m")
        if pos is not None:
            if trk["positions"]:
                last_pos, last_t = trk["positions"][-1]
                try:
                    ev_t = datetime.fromisoformat(
                        event["timestamp"].replace("Z", "+00:00")
                    ).timestamp()
                    dt = ev_t - last_t
                    if dt > 0:
                        dist = abs(pos - last_pos)
                        trk["speed_mps"] = round(dist / dt, 2)
                        trk["heading"] = (
                            "towards_front" if pos > last_pos else "towards_rear"
                        )
                except Exception:
                    pass
            ev_ts = datetime.fromisoformat(
                event["timestamp"].replace("Z", "+00:00")
            ).timestamp()
            trk["positions"].append((pos, ev_ts))
            if len(trk["positions"]) > 100:
                trk["positions"] = trk["positions"][-100:]
        cur_threat = _threat_order.get(event.get("threat_level", "low"), 0)
        max_threat = _threat_order.get(trk["max_threat"], 0)
        if cur_threat > max_threat:
            trk["max_threat"] = event.get("threat_level", "low")


async def _broadcast_ws(message: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(message)
            _stats["ws_messages_sent"] += 1
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


def _init_mock_network():
    global _network_nodes, _network_links
    for i in range(1, 11):
        nid = f"node_{i:03d}"
        _network_nodes[nid] = {
            "node_id": nid,
            "segment_id": f"seg_{i:02d}",
            "status": random.choice(["alive"] * 8 + ["degraded"]),
            "battery_pct": round(random.uniform(40, 100), 1),
            "last_heartbeat": _now_iso(),
            "events_generated": random.randint(5, 50),
        }
    node_ids = list(_network_nodes.keys())
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            if random.random() < 0.4:
                _network_links.append(
                    {
                        "from": node_ids[i],
                        "to": node_ids[j],
                        "status": random.choice(["active"] * 7 + ["degraded"] * 2 + ["broken"]),
                        "quality_pct": round(random.uniform(50, 100), 1),
                    }
                )


_init_mock_network()


def _background_maintenance():
    while True:
        time.sleep(60)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        with _lock:
            _events[:] = [
                e
                for e in _events
                if datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                > cutoff
            ]
            now_ts = time.time()
            for tid, trk in list(_tracks.items()):
                try:
                    last = datetime.fromisoformat(
                        trk["last_seen"].replace("Z", "+00:00")
                    ).timestamp()
                    if now_ts - last > 3600:
                        trk["active"] = False
                except Exception:
                    pass


_bg_thread = threading.Thread(target=_background_maintenance, daemon=True)
_bg_thread.start()


@app.post("/api/events")
async def ingest_event(event: dict):
    eid = event.get("event_id")
    if not eid:
        eid = _gen_event_id()
        event["event_id"] = eid
    if "timestamp" not in event:
        event["timestamp"] = _now_iso()
    if _is_noise(event):
        _stats["events_rejected_noise"] += 1
        return JSONResponse(
            status_code=200,
            content={"status": "rejected_noise", "event_id": eid},
        )
    if _is_duplicate(event):
        _stats["events_rejected_duplicate"] += 1
        return JSONResponse(
            status_code=200,
            content={"status": "rejected_duplicate", "event_id": eid},
        )
    with _lock:
        _seen_event_ids.add(eid)
        event.setdefault("acknowledged", False)
        event.setdefault("threat_level", "low")
        event.setdefault("target_type", "unknown")
        event.setdefault("classification_confidence", 0.0)
        event.setdefault("fused", False)
        event.setdefault("sensor_count", 1)
        event.setdefault("action_recommended", "log")
        event.setdefault("features", {})
        _events.append(event)
        _stats["events_processed"] += 1
    _update_track(event)
    await _broadcast_ws({"type": "new_event", "event": event})
    return {"status": "accepted", "event_id": eid}


@app.get("/api/events")
async def list_events(
    limit: int = Query(50, ge=1, le=500),
    min_threat: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
):
    min_lvl = _threat_order.get(min_threat, -1) if min_threat else -1
    with _lock:
        results = []
        for e in reversed(_events):
            lvl = _threat_order.get(e.get("threat_level", "low"), 0)
            if lvl < min_lvl:
                continue
            if segment and e.get("segment_id") != segment:
                continue
            if target_type and e.get("target_type") != target_type:
                continue
            if acknowledged is not None and e.get("acknowledged") != acknowledged:
                continue
            results.append(e)
            if len(results) >= limit:
                break
        return results


@app.get("/api/events/{event_id}")
async def get_event(event_id: str):
    with _lock:
        for e in _events:
            if e.get("event_id") == event_id:
                return e
    raise HTTPException(status_code=404, detail="Event not found")


@app.post("/api/events/{event_id}/ack")
async def acknowledge_event(event_id: str):
    with _lock:
        for e in _events:
            if e.get("event_id") == event_id:
                e["acknowledged"] = True
                await _broadcast_ws(
                    {"type": "event_acked", "event_id": event_id}
                )
                return {"status": "acknowledged", "event_id": event_id}
    raise HTTPException(status_code=404, detail="Event not found")


@app.post("/api/strike-request")
async def create_strike_request(body: dict):
    event_id = body.get("event_id")
    action = body.get("action")
    if not event_id or action not in ("fpv", "artillery", "recon"):
        raise HTTPException(
            status_code=400,
            detail="Required: event_id and action (fpv|artillery|recon)",
        )
    sr = {
        "request_id": f"sr_{uuid.uuid4().hex[:8]}",
        "event_id": event_id,
        "action": action,
        "notes": body.get("notes", ""),
        "status": "pending",
        "timestamp": _now_iso(),
    }
    with _lock:
        _strike_requests.append(sr)
        _stats["strike_requests"] += 1
    await _broadcast_ws({"type": "strike_request", "request": sr})
    return {"status": "submitted", "request": sr}


@app.get("/api/network/status")
async def network_status():
    alive = sum(
        1 for n in _network_nodes.values() if n["status"] in ("alive", "degraded")
    )
    active_links = sum(
        1 for l in _network_links if l["status"] == "active"
    )
    total_links = len(_network_links)
    health = (
        round((alive / max(len(_network_nodes), 1)) * 0.6 + (active_links / max(total_links, 1)) * 0.4, 3)
        if total_links > 0
        else 0.0
    )
    return {
        "health_score": health,
        "total_nodes": len(_network_nodes),
        "alive_nodes": alive,
        "total_links": total_links,
        "active_links": active_links,
        "nodes": list(_network_nodes.values()),
        "links": _network_links,
    }


@app.get("/api/tracks")
async def list_tracks(active_only: bool = Query(True)):
    with _lock:
        tracks = list(_tracks.values())
        if active_only:
            tracks = [t for t in tracks if t.get("active", True)]
        for t in tracks:
            t_copy = dict(t)
            t_copy["positions"] = [
                {"position_m": p, "timestamp_s": ts} for p, ts in t["positions"]
            ]
        return [
            {
                **{k: v for k, v in t.items() if k != "positions"},
                "positions": [
                    {"position_m": p, "timestamp_s": ts} for p, ts in t["positions"]
                ],
            }
            for t in tracks
        ]


@app.get("/api/system")
async def system_status():
    start = datetime.fromisoformat(_stats["start_time"].replace("Z", "+00:00"))
    uptime_s = (datetime.now(timezone.utc) - start).total_seconds()
    hours = int(uptime_s // 3600)
    minutes = int((uptime_s % 3600) // 60)
    seconds = int(uptime_s % 60)
    return {
        "status": "online",
        "version": "1.0.0",
        "uptime_seconds": round(uptime_s, 1),
        "uptime_human": f"{hours}h {minutes}m {seconds}s",
        "events_processed": _stats["events_processed"],
        "events_rejected_duplicate": _stats["events_rejected_duplicate"],
        "events_rejected_noise": _stats["events_rejected_noise"],
        "strike_requests_total": _stats["strike_requests"],
        "active_sensors": sum(
            1 for n in _network_nodes.values() if n["status"] in ("alive", "degraded")
        ),
        "total_sensors": len(_network_nodes),
        "ws_clients": len(_ws_clients),
        "ws_messages_sent": _stats["ws_messages_sent"],
        "tracks_active": sum(1 for t in _tracks.values() if t.get("active", True)),
    }


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    _stats["ws_connections"] += 1
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html><body style="background:#0a0a0f;color:#00ff88;font-family:monospace;padding:40px">
    <h1>TFN SpiderLink C2</h1><p>System ONLINE. <a href="/docs" style="color:#00ff88">API Docs</a></p>
    <p><a href="/ui" style="color:#00ff88">Operator UI</a></p>
    </body></html>
    """


@app.get("/ui", response_class=HTMLResponse)
async def operator_ui():
    from pathlib import Path
    ui_path = Path(__file__).parent / "operator_ui.html"
    if ui_path.exists():
        return ui_path.read_text()
    return "<html><body><h1>operator_ui.html not found</h1></body></html>"


def main():
    uvicorn.run(
        "c2.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
