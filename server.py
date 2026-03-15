#!/usr/bin/env python3
"""
Prism Siege - WebSocket backend for PvP multiplayer.
Portable: run anywhere (local, VPS, cloud). Set PORT and HOST via env.
"""
import asyncio
import json
import os
import time
from pathlib import Path

from aiohttp import web

ROOT = Path(__file__).parent.resolve()
rooms = {}  # room_id -> { players: [ws or None, ws or None], game_started: bool, empty_since: float }
matchmaking_queue = []  # [{"ws": ws, "client_id": str}, ...]
all_lobby_sockets = set()  # all ws viewing lobby (for broadcasting waiting list)
REJOIN_GRACE = 90  # seconds to keep room with disconnected slots for rejoin

WS_PATH = "/ws"


def remove_from_queue(ws):
    global matchmaking_queue
    matchmaking_queue = [e for e in matchmaking_queue if e["ws"] is not ws]


def queue_entry_by_id(client_id):
    for e in matchmaking_queue:
        if e.get("client_id") == client_id:
            return e
    return None


async def broadcast_waiting_list():
    players = [{"id": e["client_id"], "name": "Player " + e["client_id"][:6].upper()} for e in matchmaking_queue]
    msg = json.dumps({"event": "waiting_list", "players": players})
    dead = set()
    for s in all_lobby_sockets:
        if getattr(s, "closed", True):
            dead.add(s)
        else:
            try:
                await s.send_str(msg)
            except Exception:
                dead.add(s)
    for s in dead:
        all_lobby_sockets.discard(s)


async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws.client_id = os.urandom(3).hex()
    all_lobby_sockets.add(ws)
    try:
        await ws.send_str(json.dumps({"event": "identity", "client_id": ws.client_id}))
        await broadcast_waiting_list()
    except Exception:
        pass

    room_id = None
    player_idx = None
    in_matchmaking = False

    def get_room_players(r_id):
        r = rooms.get(r_id)
        return (r or {}).get("players") or []

    async def broadcast_to_room(msg, exclude_ws=None, r_id=None):
        rid = r_id or room_id
        if rid not in rooms:
            return
        for p in get_room_players(rid):
            if p is not None and p is not exclude_ws and not getattr(p, "closed", True):
                try:
                    await p.send_str(json.dumps(msg))
                except Exception:
                    pass

    try:
        async for raw in ws:
            try:
                data = json.loads(raw.data) if isinstance(raw.data, str) else raw.data
            except json.JSONDecodeError:
                continue

            cmd = data.get("cmd")

            if cmd == "find_match":
                remove_from_queue(ws)
                matchmaking_queue.append({"ws": ws, "client_id": ws.client_id})
                in_matchmaking = True
                await ws.send_str(json.dumps({
                    "event": "matchmaking",
                    "status": "searching",
                    "queue_size": len(matchmaking_queue),
                }))
                await broadcast_waiting_list()
                if len(matchmaking_queue) >= 2:
                    e1, e2 = matchmaking_queue.pop(0), matchmaking_queue.pop(0)
                    p1, p2 = e1["ws"], e2["ws"]
                    rid = os.urandom(4).hex()
                    rooms[rid] = {"players": [p1, p2], "game_started": True}
                    p1.room_id, p1.player_idx = rid, 0
                    p2.room_id, p2.player_idx = rid, 1
                    all_lobby_sockets.discard(p1)
                    all_lobby_sockets.discard(p2)
                    for i, p in enumerate([p1, p2]):
                        if not getattr(p, "closed", True):
                            try:
                                await p.send_str(json.dumps({
                                    "event": "joined",
                                    "room_id": rid,
                                    "player_idx": i,
                                    "players": 2,
                                    "ready": True,
                                }))
                            except Exception:
                                pass
                    await broadcast_waiting_list()

            elif cmd == "cancel_match":
                remove_from_queue(ws)
                in_matchmaking = False
                await ws.send_str(json.dumps({"event": "matchmaking", "status": "cancelled"}))
                await broadcast_waiting_list()

            elif cmd == "challenge":
                target_id = (data.get("target_id") or "").strip().lower()
                entry = queue_entry_by_id(target_id)
                if not entry:
                    await ws.send_str(json.dumps({"event": "error", "msg": "Player not available"}))
                    continue
                target_ws = entry["ws"]
                if getattr(target_ws, "closed", True):
                    remove_from_queue(target_ws)
                    await broadcast_waiting_list()
                    await ws.send_str(json.dumps({"event": "error", "msg": "Player left"}))
                    continue
                remove_from_queue(ws)
                remove_from_queue(target_ws)
                rid = os.urandom(4).hex()
                rooms[rid] = {"players": [ws, target_ws], "game_started": True}
                ws.room_id, ws.player_idx = rid, 0
                target_ws.room_id, target_ws.player_idx = rid, 1
                all_lobby_sockets.discard(ws)
                all_lobby_sockets.discard(target_ws)
                for i, p in enumerate([ws, target_ws]):
                    if not getattr(p, "closed", True):
                        try:
                            await p.send_str(json.dumps({
                                "event": "joined",
                                "room_id": rid,
                                "player_idx": i,
                                "players": 2,
                                "ready": True,
                            }))
                        except Exception:
                            pass
                await broadcast_waiting_list()

            elif cmd == "create":
                remove_from_queue(ws)
                in_matchmaking = False
                await broadcast_waiting_list()
                rid = os.urandom(4).hex()
                rooms[rid] = {"players": [ws, None], "game_started": False}
                room_id, player_idx = rid, 0
                await ws.send_str(json.dumps({
                    "event": "joined",
                    "room_id": rid,
                    "player_idx": 0,
                    "players": 1,
                    "ready": False,
                }))

            elif cmd == "join":
                remove_from_queue(ws)
                in_matchmaking = False
                await broadcast_waiting_list()
                rid = (data.get("room_id") or "").strip().lower()
                if rid not in rooms:
                    await ws.send_str(json.dumps({"event": "error", "msg": "Room not found"}))
                    continue
                r = rooms[rid]
                if len(r["players"]) >= 2 and r["players"][1] is not None:
                    await ws.send_str(json.dumps({"event": "error", "msg": "Room full"}))
                    continue
                r["players"][1] = ws
                room_id, player_idx = rid, 1
                r["game_started"] = True
                r.pop("empty_since", None)
                await ws.send_str(json.dumps({
                    "event": "joined",
                    "room_id": rid,
                    "player_idx": 1,
                    "players": 2,
                    "ready": True,
                }))
                await broadcast_to_room({"event": "opponent_joined", "ready": True}, exclude_ws=ws, r_id=rid)

            elif cmd == "rejoin":
                all_lobby_sockets.discard(ws)
                rid = (data.get("room_id") or "").strip().lower()
                p_idx = int(data.get("player_idx", 0))
                if rid not in rooms or p_idx not in (0, 1):
                    await ws.send_str(json.dumps({"event": "error", "msg": "Invalid rejoin"}))
                    continue
                r = rooms[rid]
                if r["players"][p_idx] is not None:
                    await ws.send_str(json.dumps({"event": "error", "msg": "Slot occupied"}))
                    continue
                r["players"][p_idx] = ws
                r.pop("empty_since", None)
                ws.room_id, ws.player_idx = rid, p_idx
                room_id, player_idx = rid, p_idx
                await ws.send_str(json.dumps({
                    "event": "joined",
                    "room_id": rid,
                    "player_idx": p_idx,
                    "players": 2,
                    "ready": True,
                }))
                await broadcast_to_room({"event": "opponent_reconnected"}, exclude_ws=ws, r_id=rid)

            elif cmd == "action":
                r_id = getattr(ws, "room_id", None) or room_id
                p_idx = getattr(ws, "player_idx", player_idx)
                if r_id and rooms.get(r_id):
                    action = data.get("action", {})
                    action["from_player"] = p_idx
                    for _ws in get_room_players(r_id):
                        if _ws is not None and _ws is not ws and not getattr(_ws, "closed", True):
                            try:
                                await _ws.send_str(json.dumps({"event": "action", "action": action}))
                            except Exception:
                                pass

    except Exception:
        pass
    finally:
        all_lobby_sockets.discard(ws)
        if in_matchmaking:
            remove_from_queue(ws)
            try:
                await broadcast_waiting_list()
            except Exception:
                pass
        r_id = getattr(ws, "room_id", None) or room_id
        if r_id and r_id in rooms:
            r = rooms[r_id]
            pl = r["players"]
            for i in range(len(pl)):
                if pl[i] is ws:
                    pl[i] = None
                    r["empty_since"] = time.monotonic()
                    break
            live = [p for p in pl if p is not None and not getattr(p, "closed", True)]
            if len(live) == 0:
                pass  # keep room for rejoin grace period
            else:
                for _ws in pl:
                    if _ws is not None and _ws is not ws and not getattr(_ws, "closed", True):
                        try:
                            await _ws.send_str(json.dumps({"event": "opponent_left"}))
                        except Exception:
                            pass

    return ws


async def cleanup_rooms(app):
    async def _cleanup():
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            to_del = []
            for rid, r in list(rooms.items()):
                pl = r.get("players") or []
                if all(p is None for p in pl) and (now - r.get("empty_since", 0)) > REJOIN_GRACE:
                    to_del.append(rid)
            for rid in to_del:
                rooms.pop(rid, None)

    asyncio.create_task(_cleanup())


async def index(request):
    return web.FileResponse(ROOT / "index.html")


async def game(request):
    return web.FileResponse(ROOT / "game-engine.html")


async def lobby(request):
    return web.FileResponse(ROOT / "lobby.html")


def main():
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    app = web.Application()
    app.on_startup.append(cleanup_rooms)
    app.router.add_get(WS_PATH, handle_ws)
    app.router.add_get("/", index)
    app.router.add_get("/index.html", index)
    app.router.add_get("/game-engine.html", game)
    app.router.add_get("/lobby.html", lobby)
    app.router.add_static("/", ROOT, show_index=False)
    web.run_app(app, host=host, port=port, print=lambda x: None)
    print(f"Prism Siege server: http://{host}:{port}")


if __name__ == "__main__":
    main()
