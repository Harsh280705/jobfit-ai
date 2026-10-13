# JobFit AI — Constraint-Aware Resume–Job Matching

JobFit AI is an explainable resume–job matching system that evaluates candidates against individual job requirements instead of relying on a single similarity score. It distinguishes mandatory and preferred skills, checks experience and education constraints, and provides evidence-backed explanations for every match.

## Key Features

- *Requirement-level matching:* Fully satisfied, partially satisfied, transferable, missing, insufficient evidence, and contradictory.
- *Constraint-aware evaluation:* AND/OR logic, experience thresholds, and education requirements.
- *Explainable results:* Evidence snippets, confidence, and reasons for each decision.
- *Resume Gap Analysis:* Identifies missing skills, transferable skills, and improvement areas.
- *Research evaluation:* Compares the existing matcher with keyword, TF-IDF, semantic, and RL approaches.

## Tech Stack

- *Frontend:* React, TypeScript, Vite, Tailwind CSS
- *Backend:* Python, FastAPI, Pydantic, SQLAlchemy
- *Database:* PostgreSQL, pgvector
- *Background tasks:* Redis, Celery
- *NLP:* spaCy, sentence-transformers, TF-IDF, regex
- *Deployment:* Docker Compose

## Run on Your PC

### Prerequisites

Install [Git](https://git-scm.com/), [Docker Desktop](https://www.docker.com/products/docker-desktop/), and ensure Docker Desktop is running.

### 1. Clone the repository

```bash
git clone https://github.com/Harsh280705/jobfit-ai.git
cd jobfit-ai
```

### 2. Configure environment variables

Create your local environment file.

*Windows PowerShell:*
```powershell
Copy-Item .env.example .env
```

*Linux/macOS:*
```bash
cp .env.example .env
```

Edit .env if needed. Use your own secure credentials for any non-local deployment.

### 3. Start the application

```bash
docker compose up --build
```

Wait for the services to start, then open:

- *Frontend:* http://localhost:5173
- *Backend API:* http://localhost:8000
- *API documentation:* http://localhost:8000/docs

Stop the application with Ctrl+C. To stop the Compose services afterward, run:

```bash
docker compose down
```

### Run Without Docker (Development)

Install Python and Node.js first. PostgreSQL and Redis must also be configured and running.

*Backend — terminal 1:*
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

*Frontend — terminal 2:*
```bash
cd frontend
npm install
npm run dev
```

For background processing, start the Celery worker in another terminal if Redis is configured. The application also supports inline processing when the broker is unavailable.

## Documentation

See the docs/ directory for:

- ARCHITECTURE.md — System architecture
- NLP_PIPELINE.md — NLP processing pipeline
- MATCHING_LOGIC.md — Matching and constraint logic
- RESEARCH.md — Evaluation methodology and results
- API.md — API reference

## Limitations and Security

The evaluation uses synthetic data and requires a larger human-annotated benchmark. Authentication, rate limiting, and production hardening remain future work. Docker Compose uses development servers and is intended for local demonstrations, not production deployment.

Never commit .env files or upload real personal resumes to public demos. See SECURITY.md for security guidance.
