# RecruiterMind — Frontend

React + Vite + Tailwind dashboard for the RecruiterMind AI candidate ranking system.

## Local development

```bash
npm install
npm run dev        # starts at http://localhost:5173
```

The frontend proxies `/api` and `/ws` to `http://localhost:8000` (the FastAPI backend).

## Vercel deployment

1. Push this repo to GitHub
2. Import the repo in Vercel, set **Root Directory** to `dashboard`
3. Add environment variables:
   - `VITE_BACKEND_URL` = your backend URL (e.g. `https://your-backend.railway.app`)
   - `VITE_BACKEND_WS_URL` = same but `wss://` prefix

## Backend

The Python FastAPI backend lives in the root of the repo. Deploy it separately on Railway or Render:

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```
