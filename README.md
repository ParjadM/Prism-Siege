# Prism Siege

3D Tower Defense — Play vs AI or PvP (2 players).

## Quick Start

**Single-player (vs AI):** Open `index.html` in a browser (file or server).

**PvP (2 players):** Run the Python server, then both players open the URL.

```bash
pip install -r requirements.txt
python server.py
```

Open http://localhost:8080 and click **Play vs Player**.

## Deploy / Play Store

- **Frontend:** Static HTML/JS (index.html, game-engine.html). Host on any web server or bundle in WebView/Capacitor.
- **Backend (PvP):** Run `server.py` on a host (VPS, Railway, Render, etc.). Set `PORT` and `HOST` via env.
- **Config:** Set `window.PRISM_SIEGE_WS_URL` before load to override WebSocket URL (e.g. `wss://your-server.com/ws`).
