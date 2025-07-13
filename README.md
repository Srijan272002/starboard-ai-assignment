# Starboard

Starboard is a full-stack real estate analytics platform for property comparison, market analysis, and investment insights. It features a Next.js + TypeScript frontend and a FastAPI + PostgreSQL backend, with advanced data processing and visualization.

---

## Features

- **Property Comparison:** Instantly compare properties by price, size, and more.
- **Market Trends:** Visualize real estate market trends with interactive charts.
- **Data Export:** Download property and market data for offline analysis.
- **Robust Backend:** FastAPI, async SQLAlchemy, Redis caching, and scheduled tasks.
- **Modern Frontend:** Next.js 14, TypeScript, Tailwind CSS, D3.js, and Mapbox integration.

---

## Project Structure

```
starboard/
  backend/    # FastAPI backend, database, and API logic
  frontend/   # Next.js frontend, UI, and static assets
```

---

## Getting Started

### Prerequisites

- Node.js (v18+ recommended)
- Python 3.10+
- PostgreSQL (for backend database)
- Redis (for caching)
- (Optional) Mapbox API key for map features

---

### 1. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

- Visit [http://localhost:3000](http://localhost:3000) to view the app.

#### Environment Variables

Create a `.env` file in `frontend/` for any required API keys (e.g., `NEXT_PUBLIC_MAPBOX_TOKEN`).

---

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # On Windows
# or
source venv/bin/activate  # On Mac/Linux

pip install -r requirements.txt
uvicorn main:app --reload
```

- The API will be available at [http://localhost:8000](http://localhost:8000).

#### Environment Variables

Copy `.env.example` to `.env` and configure your database and Redis settings.

---

### 3. Database Migrations

```bash
cd backend
alembic upgrade head
```

---

## Development

- **Frontend:** Edit `frontend/src/app/page.tsx` and components. Supports hot reload.
- **Backend:** Edit `backend/` modules. Supports auto-reload with `uvicorn`.

---

## Testing

- **Frontend:** `npm run test` (if tests are set up)
- **Backend:** `pytest` in the `backend/` directory

---

## Deployment

- **Frontend:** Deploy on Vercel, Netlify, or any Node.js host.
- **Backend:** Deploy on any server supporting Python 3.10+, e.g., Heroku, AWS, DigitalOcean.

---

## Contributing

Pull requests and issues are welcome! Please see the `improvements.md` and `roadmap.md` for ideas and guidelines.

---

## License

MIT License 