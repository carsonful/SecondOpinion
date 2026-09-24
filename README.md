# SecondOpinion
Busting health myths backed by science.

## Project structure

- `frontend/` — React + TypeScript (Vite)
- `backend/` — Python API (FastAPI)

## Getting started

### Backend

```
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs on http://localhost:8000. Health check at `/api/health`.

### Frontend

```
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173 and proxies `/api` requests to the backend.

## Tests and coverage

Run the backend tests from the project root after activating the backend virtual environment:

```
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests --cov=backend/app --cov-config=backend/pyproject.toml --cov-report=xml:backend/coverage.xml
```

Run the frontend tests from `frontend/`:

```
npm ci
npm run test:coverage
```

The GitHub Actions workflow runs both suites and sends their coverage reports to SonarQube.
For quick local reruns, use `python -m pytest backend/tests` from the project root or `npm test` from `frontend/`.
