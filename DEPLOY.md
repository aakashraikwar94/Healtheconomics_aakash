# Deployment Guide

## Option A — Run Locally (quickest)

```bash
pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY
python app.py
```
Open http://localhost:5000 — on first visit you'll be prompted to create an admin account.

---

## Option B — Deploy to Railway (free tier, online in ~5 minutes)

Railway hosts Python apps for free and gives you a public URL.

1. Push this repo to GitHub (if not already there)
2. Go to https://railway.app → **New Project** → **Deploy from GitHub repo**
3. Select this repository
4. In **Variables**, add:
   ```
   ANTHROPIC_API_KEY = sk-ant-your-key-here
   FLASK_SECRET_KEY  = any-long-random-string
   ```
5. Railway auto-detects the `Procfile` and deploys
6. Click **Generate Domain** to get a public URL like `https://your-app.up.railway.app`

> **Persistent storage:** For the SQLite database to survive redeploys, add a Railway Volume and set `DATABASE_PATH=/data/chatbot.db`.

---

## Option C — Deploy to Render (free tier)

1. Push to GitHub
2. Go to https://render.com → **New** → **Web Service**
3. Connect your GitHub repo
4. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app`
5. Add environment variables (`ANTHROPIC_API_KEY`, `FLASK_SECRET_KEY`)
6. Click **Create Web Service**

---

## Option D — Deploy with Docker

```bash
# Build the image
docker build -t asd-chatbot .

# Run with a persistent volume for the database
docker run -d \
  -p 8000:8000 \
  -v chatbot-data:/data \
  -e ANTHROPIC_API_KEY=sk-ant-your-key \
  -e FLASK_SECRET_KEY=your-random-secret \
  --name asd-chatbot \
  asd-chatbot
```

Open http://localhost:8000

---

## Adding More Users

After the first admin account is created, add more accounts via the Python shell:

```bash
# In the project directory:
python - <<'EOF'
from database import init_db, create_user
from werkzeug.security import generate_password_hash
init_db()
create_user("newusername", generate_password_hash("their-password"))
print("User created.")
EOF
```

---

## Environment Variables

| Variable           | Required | Description                                      |
|--------------------|----------|--------------------------------------------------|
| `ANTHROPIC_API_KEY`| Yes      | Your Anthropic API key                           |
| `FLASK_SECRET_KEY` | Yes      | Random string for session security (min 32 chars)|
| `DATABASE_PATH`    | No       | Path to SQLite file (default: `chatbot.db`)      |
| `PORT`             | No       | Port to listen on (default: `5000`)              |
| `FLASK_DEBUG`      | No       | Set to `true` for development only               |
