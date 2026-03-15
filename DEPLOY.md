# Deploy Prism Siege for Free (Testing)

Your app is **one Python server** that serves both the website and the WebSocket. Deploy the whole folder to a free host that runs Python.

---

## Option 1: Render (recommended, free tier)

1. **Push your project to GitHub**  
   Create a repo and push the `Prism Siege` folder (include `server.py`, `requirements.txt`, `index.html`, `lobby.html`, `game-engine.html`).

2. **Go to [render.com](https://render.com)** and sign up (free).

3. **New → Web Service**  
   - Connect your GitHub repo.  
   - **Root Directory:** leave empty (or the folder that contains `server.py` if the repo root is above it).  
   - **Runtime:** Python 3.  
   - **Build command:**  
     ```bash
     pip install -r requirements.txt
     ```  
   - **Start command:**  
     ```bash
     python server.py
     ```  
   - **Instance type:** Free.

4. **Deploy**  
   Render will assign a URL like `https://prism-siege-xxxx.onrender.com`.

5. **Use it**  
   Open that URL in the browser. Play vs AI and PvP (lobby + matchmaking) work; the site and WebSocket are on the same host, so no extra config.

**Note:** On the free tier the service sleeps after ~15 min of no traffic; the first open may take 30–60 seconds to wake up.

---

## Option 2: Railway (free tier with monthly credit)

1. **Push the project to GitHub** (same as above).

2. **Go to [railway.app](https://railway.app)** and sign up.

3. **New Project → Deploy from GitHub**  
   Select the repo (and the directory that has `server.py` if needed).

4. **Settings**  
   - **Build:**  
     - Build Command: `pip install -r requirements.txt` (or leave empty and add a `nixpacks.toml` / use default).  
   - **Start Command:** `python server.py`  
   - **Root Directory:** set if `server.py` is not in the repo root.

5. **Deploy**  
   Railway will give a public URL. Enable **Generate Domain** in Settings → Networking.

6. **Use it**  
   Open the generated URL. Same as Render: one host for site + WebSocket.

---

## Option 3: Fly.io (free tier)

1. **Install [flyctl](https://fly.io/docs/hands-on/install-flyctl/)** and log in: `fly auth login`.

2. **In your project folder** (where `server.py` and `requirements.txt` are), run:
   ```bash
   fly launch --no-deploy
   ```
   Choose app name, region; say no to PostgreSQL.

3. **Set the port**  
   Fly injects `PORT`. Your server already uses `os.environ.get("PORT", "8080")`, so it’s fine.

4. **Create `Dockerfile`** (so Fly can run Python):
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   CMD ["python", "server.py"]
   ```

5. **Deploy:**
   ```bash
   fly deploy
   ```

6. **Open the app:**  
   `https://<your-app-name>.fly.dev`

---

## Checklist before deploy

- [ ] `requirements.txt` has `aiohttp>=3.9.0`
- [ ] All in one folder: `server.py`, `requirements.txt`, `index.html`, `lobby.html`, `game-engine.html`
- [ ] No hardcoded `localhost` in the frontend (the game uses `location.host` for the WebSocket when served from the same host, so it’s fine)

## If you split frontend and backend later

If you host the HTML on e.g. **Netlify** and the Python server on **Render**, set the WebSocket URL in the frontend before building/deploying:

```html
<script>
  window.PRISM_SIEGE_WS_URL = 'wss://your-server.onrender.com/ws';
</script>
```

Then the lobby and game will connect to that URL instead of `location.host`.

---

**Quick test:** After deploy, open the URL on two devices (or two browser windows) → Lobby → Find Match or Challenge. If both join the same game, deployment is working.
