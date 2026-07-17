# TrueLens

TrueLens is an advanced AI-powered article analysis and fact-checking application. It consists of a Next.js frontend (React 19) and a FastAPI (Python 3.12) backend, utilizing Gemini for AI analysis, Redis for caching, and PostgreSQL/SQLite for data storage.

## Architecture

- **Frontend (`TrueLens/`)**: Next.js App Router, Tailwind CSS, Framer Motion, Clerk Authentication.
- **Backend (`backend/`)**: FastAPI, SQLAlchemy, Redis Cache, Google Gemini API, ChromaDB for embeddings.

## Local Setup

### 1. Prerequisites
- Node.js 18+
- Python 3.12+
- (Optional) Docker and Docker Compose

### 2. Environment Variables

**Frontend (`TrueLens/.env.local`)**:
See `TrueLens/.env.local.example` for required keys (Clerk & API URL).

**Backend (`backend/.env`)**:
See `backend/.env.example` for required keys (Database, Redis, Gemini API, Clerk).

### 3. Running Locally (Manual)

#### Backend
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate | Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd TrueLens
npm install
npm run dev
```

### 4. Running Locally (Docker Compose)
To run the backend and Redis easily via Docker:
```bash
docker-compose up --build
```

## Deployment Guide

### Frontend (Vercel)
The frontend is optimized for deployment on Vercel.
1. Connect your GitHub repository to Vercel.
2. Set the Root Directory to `TrueLens`.
3. Configure the environment variables from `.env.local`.
4. Deploy!

### Backend (Railway)
The backend includes a `railway.json` and `Dockerfile` for seamless deployment.
1. Connect the repository to Railway.
2. Ensure the root directory is set to `/backend` in the service settings.
3. Configure your Environment Variables.
4. Deploy!

## Optimization Details
- **Lazy Loading**: Heavy components like data tables are dynamically imported using `next/dynamic`.
- **API Caching**: Redis caches analysis requests to avoid redundant AI calls.
- **Background Tasks**: Embeddings generation and database saving run as background tasks to keep API responses fast.
