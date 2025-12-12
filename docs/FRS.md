# Cognify - Functional Requirements Specification (FRS)

## 1. API Endpoints

### 1.1 Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/auth/register` | Register new user | No |
| POST | `/api/v1/auth/login` | Authenticate user | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | No (refresh token) |
| GET | `/api/v1/auth/me` | Get current user | Yes |
| PATCH | `/api/v1/auth/me` | Update current user | Yes |
| POST | `/api/v1/auth/change-password` | Change password | Yes |
| DELETE | `/api/v1/auth/account` | Delete account | Yes |

### 1.2 Document Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/documents/upload` | Upload document | Yes |
| GET | `/api/v1/documents` | List documents (paginated) | Yes |
| GET | `/api/v1/documents/recent` | Get recent documents | Yes |
| GET | `/api/v1/documents/{id}` | Get document details | Yes |
| GET | `/api/v1/documents/{id}/status` | Get processing status | Yes |
| GET | `/api/v1/documents/{id}/download` | Download original file | Yes |
| GET | `/api/v1/documents/ingestion/{id}` | Get by ingestion_id | Yes |
| DELETE | `/api/v1/documents/{id}` | Delete document | Yes |

### 1.3 Processing Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/documents/{id}/processing-status` | Detailed step status | Yes |
| POST | `/api/v1/documents/{id}/process/extract-text` | Step 1: Extract text | Yes |
| POST | `/api/v1/documents/{id}/process/extract-themes` | Step 2: Extract themes | Yes |
| POST | `/api/v1/documents/{id}/process/generate-lesson` | Step 3: Generate lesson | Yes |
| POST | `/api/v1/documents/{id}/process/extract-citations` | Step 4: Extract citations | Yes |
| POST | `/api/v1/documents/{id}/process/generate-audio` | Step 5: Generate audio | Yes |
| POST | `/api/v1/documents/{id}/process/retry` | Retry failed step | Yes |

### 1.4 Lesson Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/lessons` | List lessons (paginated) | Yes |
| GET | `/api/v1/lessons/{id}` | Get lesson details | Yes |
| GET | `/api/v1/lessons/document/{id}` | Get lesson by document | Yes |
| PATCH | `/api/v1/lessons/{id}/progress` | Update progress | Yes |
| POST | `/api/v1/lessons/{id}/complete` | Mark complete | Yes |
| POST | `/api/v1/lessons/{id}/reset-progress` | Reset progress | Yes |

---

## 2. Data Model

### 2.1 Entity Definitions

#### User
```
User
├── id: UUID (PK)
├── email: String (unique, indexed)
├── hashed_password: String
├── full_name: String
├── company: String (nullable)
├── role: String (nullable)
├── is_active: Boolean (default: true)
├── is_verified: Boolean (default: false)
├── email_notifications: Boolean (default: true)
├── daily_goal_minutes: Integer (default: 30)
├── theme: String (default: "system")
├── created_at: DateTime
├── updated_at: DateTime
└── last_login: DateTime (nullable)
```

#### Document
```
Document
├── id: UUID (PK)
├── ingestion_id: String (unique, indexed)
├── user_id: UUID (FK → User)
├── title: String
├── file_name: String
├── file_type: Enum (PDF, DOCX, TXT)
├── file_size: Integer (bytes)
├── file_path: String
├── raw_content: Text (nullable)
├── word_count: Integer (nullable)
├── status: Enum (PENDING, PROCESSING, COMPLETED, FAILED)
├── current_step: String (nullable)
├── step_statuses: JSON (nullable)
├── failed_step: String (nullable)
├── step_error_message: Text (nullable)
├── retry_count: Integer (default: 0)
├── idempotency_key: String (nullable, indexed)
├── created_at: DateTime
├── updated_at: DateTime
└── processed_at: DateTime (nullable)
```

#### Theme
```
Theme
├── id: UUID (PK)
├── document_id: UUID (FK → Document)
├── name: String (max 100)
├── description: Text
├── order: Integer
└── created_at: DateTime
```

#### Lesson
```
Lesson
├── id: UUID (PK)
├── document_id: UUID (FK → Document, unique)
├── title: String
├── summary: Text
├── content: Text (250-400 words)
├── word_count: Integer
├── what_youll_learn: Text
├── key_takeaways: JSON (array of strings)
├── apply_at_work: Text
├── learning_outcomes: JSON (array of objects)
├── outcomes_completed: JSON (array of IDs)
├── audio_path: String (nullable)
├── audio_duration: Integer (seconds, nullable)
├── is_completed: Boolean (default: false)
├── progress_percentage: Float (0-100)
├── audio_position: Integer (seconds)
├── time_spent_seconds: Integer
├── completed_at: DateTime (nullable)
├── last_accessed_at: DateTime (nullable)
├── created_at: DateTime
└── updated_at: DateTime
```

#### Citation
```
Citation
├── id: UUID (PK)
├── document_id: UUID (FK → Document)
├── snippet: Text (exact quote)
├── location: String (e.g., "Middle", "Beginning")
├── relevance_score: Integer (0-100)
├── order: Integer
├── context_before: Text (nullable)
├── context_after: Text (nullable)
└── created_at: DateTime
```

### 2.2 Relationships

```
User (1) ──────── (N) Document
Document (1) ──── (N) Theme
Document (1) ──── (1) Lesson
Document (1) ──── (N) Citation
User (1) ──────── (N) Activity
User (1) ──────── (N) Notification
```

---

## 3. Error States

### 3.1 HTTP Status Codes

| Code | Description | When Used |
|------|-------------|-----------|
| 200 | OK | Successful GET/PATCH requests |
| 201 | Created | Successful POST (create) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation errors, invalid input |
| 401 | Unauthorized | Missing or invalid JWT |
| 403 | Forbidden | Accessing another user's resources |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate resource (e.g., email) |
| 422 | Unprocessable Entity | Business logic errors |
| 500 | Internal Server Error | Unexpected server errors |

### 3.2 Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

### 3.3 Processing Error States

| Step | Possible Errors | Recovery |
|------|-----------------|----------|
| extract_text | File not found, unsupported format | Re-upload file |
| extract_themes | AI API timeout, rate limit | Retry (max 3) |
| generate_lesson | AI API timeout, rate limit | Retry (max 3) |
| extract_citations | AI API timeout, rate limit | Retry (max 3) |
| generate_audio | TTS service unavailable | Retry (max 3) |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time | < 500ms | Non-AI endpoints |
| Document Upload | < 5s | 10MB file |
| Text Extraction | < 5s | 100-page PDF |
| AI Processing | < 30s per step | GPT-4o dependent |
| Audio Generation | < 10s | 400-word lesson |
| Total Processing | < 90s | Full pipeline |

### 4.2 Scalability

| Metric | Current | Production Target |
|--------|---------|-------------------|
| Concurrent Users | 10 | 1,000 |
| Documents per User | 100 | 10,000 |
| Database Size | 100MB | 10GB |

### 4.3 Availability

| Metric | Target |
|--------|--------|
| Uptime | 99.5% |
| Planned Maintenance | < 1 hour/week |
| Recovery Time | < 30 minutes |

### 4.4 Security

| Requirement | Implementation |
|-------------|----------------|
| Authentication | JWT (30-min access, 7-day refresh) |
| Password Storage | bcrypt (work factor 12) |
| Data Isolation | User-scoped queries |
| File Validation | MIME type checking |
| Input Validation | Pydantic schemas |
| CORS | Configurable origins |

---

## 5. API Request/Response Examples

### 5.1 Document Upload

**Request:**
```http
POST /api/v1/documents/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <binary>
title: "Leadership Guide 2024"
```

**Response (201):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "ingestion_id": "ing_a1b2c3d4e5f6",
  "title": "Leadership Guide 2024",
  "file_name": "leadership.pdf",
  "file_type": "PDF",
  "file_size": 245760,
  "status": "pending",
  "word_count": null,
  "created_at": "2024-01-15T10:30:00Z",
  "themes_count": 0,
  "has_lesson": false
}
```

### 5.2 Processing Step

**Request:**
```http
POST /api/v1/documents/123e4567.../process/extract-themes
Authorization: Bearer <token>
Content-Type: application/json

{
  "idempotency_key": "unique-request-id-123"
}
```

**Response (200):**
```json
{
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "step": "extract_themes",
  "status": "completed",
  "message": "Successfully identified 5 themes",
  "next_step": "generate_lesson",
  "retry_count": 0
}
```

### 5.3 Get Lesson with Audio

**Request:**
```http
GET /api/v1/lessons/789e1234...
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "id": "789e1234-...",
  "document_id": "123e4567-...",
  "title": "Effective Leadership in the Modern Workplace",
  "summary": "This lesson explores key leadership principles...",
  "content": "Leadership is the cornerstone of organizational success...",
  "word_count": 325,
  "what_youll_learn": "How to apply modern leadership techniques...",
  "key_takeaways": [
    "Communication is the foundation of leadership",
    "Trust is built through consistent actions",
    "Adaptability separates good leaders from great ones"
  ],
  "apply_at_work": "Start by scheduling one-on-one meetings...",
  "learning_outcomes": [
    {"id": "lo1", "title": "Understand leadership styles", "description": "..."},
    {"id": "lo2", "title": "Apply communication techniques", "description": "..."}
  ],
  "audio_url": "http://localhost:8000/static/audio/narration_abc123.mp3",
  "audio_duration": 120,
  "is_completed": false,
  "progress_percentage": 45.5,
  "themes": [
    {"id": "...", "name": "Leadership Excellence", "description": "..."},
    {"id": "...", "name": "Team Communication", "description": "..."}
  ],
  "citations": [
    {
      "id": "...",
      "snippet": "Trust is built through consistent actions...",
      "location": "Middle",
      "relevance_score": 85
    }
  ]
}
```
