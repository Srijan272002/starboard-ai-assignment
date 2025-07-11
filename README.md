# Starboard AI - Multi-County Property Analysis System

An intelligent agent system for analyzing industrial properties across three major US markets:
- Cook County, Illinois (Chicago) - Largest market nationally
- Dallas County, Texas - Fastest growing market
- Los Angeles County, California - Largest inventory

## Project Structure

```
starboard/
├── frontend/                 # Next.js frontend application
│   ├── src/
│   ├── package.json
│   └── ...
├── backend/                  # FastAPI backend application
│   ├── app/
│   │   ├── api/             # API routes and endpoints
│   │   ├── core/            # Configuration, logging, exceptions
│   │   ├── db/              # Database models and configuration
│   │   └── main.py          # FastAPI application entry point
│   ├── tests/               # Backend tests
│   ├── requirements.txt     # Python dependencies
│   └── pyproject.toml       # Python project configuration
├── venv/                    # Python virtual environment
├── ROADMAP.md              # Project roadmap and phases
└── README.md               # This file
```

## Technology Stack

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy** - SQL toolkit and ORM
- **PostgreSQL** - Primary database
- **Structlog** - Structured logging
- **Pytest** - Testing framework
- **Black/isort** - Code formatting
- **MyPy** - Type checking

### Frontend
- **Next.js 15** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework
- **ESLint** - Code linting
- **Prettier** - Code formatting

## Development Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL (for production)

### Backend Setup

1. **Activate the virtual environment:**
   ```bash
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the backend directory:
   ```env
   DATABASE_URL=postgresql://starboard:password@localhost/starboard_db
   LOG_LEVEL=INFO
   COOK_COUNTY_API_URL=
   DALLAS_COUNTY_API_URL=
   LA_COUNTY_API_URL=
   ```

4. **Run the development server:**
   ```bash
   uvicorn app.main:app --reload
   ```

   The API will be available at `http://localhost:8000`
   API documentation: `http://localhost:8000/docs`

### Frontend Setup

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Run the development server:**
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Code Quality
```bash
# Format code
black .
isort .

# Type checking
mypy .
```

## API Endpoints

### Health Checks
- `GET /` - Basic application info
- `GET /health` - Simple health check
- `GET /api/v1/health/` - API health check
- `GET /api/v1/health/detailed` - Detailed system health

### Properties (Phase 3)
- `GET /api/v1/properties/` - List properties
- `GET /api/v1/properties/{id}` - Get property details

### Comparables (Phase 4)
- `GET /api/v1/comparables/{property_id}` - Get comparable properties

## Database Schema

### Properties Table
- Basic property information (address, county, type)
- Physical details (square footage, lot size, year built)
- Location data (coordinates)
- Financial data (assessed value, market value)
- Property features (JSON field for flexibility)
- Data quality metrics
- Processing metadata

### Property Comparables Table
- Similarity scores across multiple dimensions
- Distance calculations
- Confidence metrics
- Analysis versioning

### API Logs Table
- Request/response tracking
- Performance monitoring
- Error logging
- Rate limit tracking

## Development Phases

- **Phase 1**: ✅ Project Setup and Infrastructure (Current)
- **Phase 2**: API Discovery Agent (Weeks 2-3)
- **Phase 3**: Data Extraction System (Weeks 4-5)
- **Phase 4**: Comparable Discovery Agent (Weeks 6-7)
- **Phase 5**: Frontend Development (Weeks 8-9)
- **Phase 6**: Testing and Optimization (Week 10)
- **Phase 7**: Deployment and Launch (Week 11)

See [ROADMAP.md](ROADMAP.md) for detailed phase breakdown.

## Key Features (Planned)

### Intelligent Data Processing
- Automated API discovery and documentation
- Smart field normalization and mapping
- Comprehensive data validation
- Quality scoring and anomaly detection

### Advanced Property Comparison
- Multi-dimensional similarity analysis
- Geographic clustering and market analysis
- Confidence scoring for comparables
- Machine learning-powered matching

### Robust Architecture
- Comprehensive error handling and logging
- Intelligent rate limiting with auto-detection
- Real-time API health monitoring
- Scalable microservices design

## Contributing

1. Follow the established code style (Black, isort, Prettier)
2. Write tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass before submitting changes

## License

[License information to be added] 