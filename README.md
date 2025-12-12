# Cognify Backend API

AI-powered learning content generation API that transforms documents into structured, workplace-focused lessons with audio narration.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.2-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai)](https://openai.com)

---

## Overview

Cognify Backend is a FastAPI-based REST API that powers an AI learning platform. It handles document ingestion (PDF, DOCX, TXT), extracts key themes using GPT-4o, generates concise workplace-oriented lessons, and produces audio narration using Google Text-to-Speech (gTTS).

### Key Features

- **Multi-format Document Ingestion**: Upload PDF, DOCX, and TXT files (up to 10MB)
- **AI-Powered Analysis**: Extract 3-7 themes using OpenAI GPT-4o with structured JSON output
- **Lesson Generation**: Create 250-400 word workplace-focused lessons
- **Audio Narration**: Generate British English audio using gTTS
- **Citation Extraction**: Identify and validate top 2-3 source snippets
- **Progress Tracking**: Track lesson completion, audio position, and time spent
- **User Authentication**: JWT-based auth with access/refresh token rotation
- **Activity History**: Full audit trail of user actions

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastAPI 0.115.2 | High-performance async REST API |
| **Database** | SQLite + aiosqlite | Async persistence (PostgreSQL-ready) |
| **ORM** | SQLAlchemy 2.0 | Async database operations |
| **Authentication** | python-jose + bcrypt | JWT tokens with secure password hashing |
| **AI/LLM** | OpenAI GPT-4o | Theme extraction, lesson generation |
| **TTS** | gTTS | Google Text-to-Speech (British English) |
| **PDF Processing** | PyMuPDF (fitz) | Fast, accurate PDF text extraction |
| **DOCX Processing** | python-docx | Word document parsing |
| **Validation** | Pydantic 2.9 | Request/response schema validation |

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- OpenAI API key

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd cognify-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Required
JWT_SECRET_KEY=your-super-secret-key-change-in-production
OPENAI_API_KEY=sk-your-openai-api-key

# Optional
DATABASE_URL=sqlite+aiosqlite:///./cognify.db
LLM_PROVIDER=openai
CORS_ORIGINS=http://localhost:3000
MAX_FILE_SIZE_MB=10
APP_ENV=development
DEBUG=true
```

### 3. Run the Server

```bash
# Development mode with auto-reload
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 4. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

---

## Project Structure

```
cognify-backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── __init__.py          # API router aggregator
│   │       ├── auth.py              # Authentication endpoints
│   │       ├── documents.py         # Document CRUD & upload
│   │       ├── processing.py        # Step-by-step AI processing
│   │       ├── lessons.py           # Lesson retrieval & progress
│   │       ├── dashboard.py         # Dashboard statistics
│   │       ├── activities.py        # Activity history
│   │       ├── users.py             # User settings
│   │       ├── notifications.py     # Notification management
│   │       ├── search.py            # Global search
│   │       └── health.py            # Health check
│   ├── core/
│   │   ├── config.py                # Settings & configuration
│   │   └── dependencies.py          # FastAPI dependencies
│   ├── db/
│   │   └── session.py               # Database setup & sessions
│   ├── models/
│   │   ├── user.py                  # User model
│   │   ├── document.py              # Document model
│   │   ├── theme.py                 # Theme model
│   │   ├── lesson.py                # Lesson model
│   │   ├── citation.py              # Citation model
│   │   ├── activity.py              # Activity model
│   │   ├── notification.py          # Notification model
│   │   └── refresh_token.py         # JWT refresh token model
│   ├── schemas/
│   │   └── [Pydantic schemas]       # Request/response validation
│   └── services/
│       ├── auth_service.py          # Authentication logic
│       ├── document_service.py      # Document lifecycle
│       ├── file_processor.py        # Text extraction (PDF/DOCX/TXT)
│       ├── ai_service.py            # LLM integration
│       ├── audio_service.py         # TTS generation (gTTS)
│       ├── step_processor.py        # Processing step execution
│       ├── activity_service.py      # Activity logging
│       └── notification_service.py  # Notification management
├── tests/
│   └── test_services.py             # Service tests
├── uploads/                         # Uploaded document storage
│   └── audio/                       # Generated audio files
├── docs/                            # Documentation
│   ├── ARCHITECTURE_NOTE.md         # Architecture documentation
│   ├── BRS.md                       # Business Requirements
│   ├── FRS.md                       # Functional Requirements
│   └── Cognify_Presentation.pptx    # Slide deck
├── main.py                          # Application entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
└── README.md                        # This file
```

---

## API Endpoints

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register new user |
| POST | `/login` | Authenticate user |
| POST | `/refresh` | Refresh access token |
| GET | `/me` | Get current user |
| PATCH | `/me` | Update current user |
| POST | `/change-password` | Change password |
| DELETE | `/account` | Delete account |

### Documents (`/api/v1/documents`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload document (PDF/DOCX/TXT) |
| GET | `/` | List user's documents (paginated) |
| GET | `/recent` | Get recent documents |
| GET | `/{id}` | Get document details with themes |
| GET | `/{id}/status` | Get processing status |
| GET | `/{id}/download` | Download original file |
| GET | `/ingestion/{ingestion_id}` | Get by ingestion ID |
| DELETE | `/{id}` | Delete document |

### Processing (`/api/v1/documents/{id}/process`)

Step-by-step AI processing (frontend-controlled):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/../processing-status` | Get detailed step status |
| POST | `/extract-text` | Step 1: Extract text from file |
| POST | `/extract-themes` | Step 2: AI theme extraction |
| POST | `/generate-lesson` | Step 3: AI lesson generation |
| POST | `/extract-citations` | Step 4: AI citation extraction |
| POST | `/generate-audio` | Step 5: gTTS audio generation |
| POST | `/retry-step` | Retry failed step |

### Lessons (`/api/v1/lessons`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's lessons (paginated) |
| GET | `/{id}` | Get lesson with themes & citations |
| GET | `/document/{document_id}` | Get lesson by document |
| PATCH | `/{id}/progress` | Update progress (%, position, time) |
| POST | `/{id}/complete` | Mark lesson complete |
| POST | `/{id}/outcomes` | Update learning outcomes |
| POST | `/{id}/reset-progress` | Reset lesson progress |

### Dashboard (`/api/v1/dashboard`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Get full dashboard data |
| GET | `/stats` | Get statistics |
| GET | `/recent-documents` | Get recent documents |
| GET | `/recent-lessons` | Get recent lessons |

### User Settings (`/api/v1/user/settings`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Get all settings |
| GET/PATCH | `/profile` | Profile settings |
| GET/PATCH | `/notifications` | Notification preferences |
| GET/PATCH | `/learning` | Learning preferences |

### Other Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/activities` | List activities (paginated) |
| GET | `/api/v1/notifications` | List notifications |
| GET | `/api/v1/search?q={query}` | Global search |
| GET | `/api/v1/health` | Health check |

---

## Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DOCUMENT PROCESSING PIPELINE                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────┐    ┌───────────────┐    ┌─────────────────┐          │
│   │   STEP 1     │    │    STEP 2     │    │     STEP 3      │          │
│   │ EXTRACT_TEXT │───▶│EXTRACT_THEMES │───▶│ GENERATE_LESSON │          │
│   │              │    │               │    │                 │          │
│   │ PyMuPDF/docx │    │ GPT-4o JSON   │    │ GPT-4o Pydantic │          │
│   │ MIME check   │    │ 3-7 themes    │    │ 250-400 words   │          │
│   └──────────────┘    └───────────────┘    └────────┬────────┘          │
│                                                      │                   │
│                                                      ▼                   │
│   ┌──────────────┐    ┌───────────────┐    ┌─────────────────┐          │
│   │   STEP 5     │    │    STEP 4     │    │                 │          │
│   │GENERATE_AUDIO│◀───│EXTRACT_CITATIONS◀──┤                 │          │
│   │              │    │               │    │                 │          │
│   │ gTTS British │    │ 2-3 validated │    │                 │          │
│   │ MP3 output   │    │ source quotes │    │                 │          │
│   └──────────────┘    └───────────────┘    └─────────────────┘          │
│                                                                          │
│   Each step: Idempotent │ Retry 3x │ Exponential Backoff (1s, 2s, 4s)   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model

```
User (1) ──────── (N) Document
                       │
                       ├──── (N) Theme (3-7 per document)
                       │
                       ├──── (1) Lesson (with progress tracking)
                       │
                       └──── (N) Citation (2-3 per document)

User (1) ──────── (N) Activity (audit trail)
     │
     └──────────  (N) Notification
```

### Key Entities

| Entity | Description |
|--------|-------------|
| **User** | Authentication, profile, preferences, notification settings |
| **Document** | Uploaded file metadata, raw content, processing status |
| **Theme** | AI-extracted themes with name and description |
| **Lesson** | Generated lesson with audio, progress, learning outcomes |
| **Citation** | Validated source snippets with location references |
| **Activity** | User action history for timeline tracking |

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `JWT_SECRET_KEY` | Secret for JWT signing | Yes | - |
| `OPENAI_API_KEY` | OpenAI API key | Yes | - |
| `DATABASE_URL` | Database connection string | No | `sqlite+aiosqlite:///./cognify.db` |
| `LLM_PROVIDER` | AI provider (`openai` or `anthropic`) | No | `openai` |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Claude) | No | - |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | No | `http://localhost:3000` |
| `MAX_FILE_SIZE_MB` | Maximum upload file size | No | `10` |
| `UPLOAD_DIR` | Directory for uploaded files | No | `./uploads` |
| `AUDIO_OUTPUT_DIR` | Directory for audio files | No | `./uploads/audio` |
| `BASE_URL` | Base URL for audio file URLs | No | `http://localhost:8000` |
| `APP_ENV` | Environment (`development`/`production`) | No | `development` |
| `DEBUG` | Enable debug mode | No | `true` |

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_services.py -v
```

---

## Documentation

Full documentation is available in the `/docs` folder:

- **[Architecture Note](docs/ARCHITECTURE_NOTE.md)** - System design, data flow, trade-offs
- **[BRS](docs/BRS.md)** - Business Requirements Specification
- **[FRS](docs/FRS.md)** - Functional Requirements Specification
- **[Slides](docs/Cognify_Presentation.pptx)** - Technical presentation (5 slides)

---

## Production Deployment

### Checklist

- [ ] Change `JWT_SECRET_KEY` to a secure random value
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Configure proper `CORS_ORIGINS`
- [ ] Consider PostgreSQL instead of SQLite
- [ ] Set up file storage (S3 or similar)
- [ ] Configure proper logging
- [ ] Enable HTTPS
- [ ] Set up monitoring/alerting

### Running with Gunicorn

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## License

This project was created as part of a Full-Stack Engineer Technical Challenge.

---

## Related

- [Cognify Frontend](../cognify) - Next.js frontend application
