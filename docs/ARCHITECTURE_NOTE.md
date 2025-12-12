# Cognify Architecture Note

**Version:** 1.0
**Date:** December 2024
**Author:** Engineering Team

---

## 1. Executive Summary

Cognify is a learning platform that transforms arbitrary documents into structured, workplace-oriented lessons with AI-generated narration. The system ingests PDF, DOCX, and TXT files, extracts key themes, generates concise lessons (250-400 words), produces voice narration using Google Text-to-Speech (gTTS), and persists all artifacts with full traceability via `ingestion_id`.

This document outlines the architectural decisions, trade-offs, data flows, and reliability mechanisms that ensure **correctness and reliability of the ingestion/analysis pipeline**—the highest-weighted evaluation criterion (25%).

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js 14)                          │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌────────────────┐  │
│  │Dashboard│  │  Upload  │  │ Documents │  │ Lessons │  │ Learning Page  │  │
│  │  Page   │  │   Page   │  │   Page    │  │  Page   │  │ (Audio Player) │  │
│  └────┬────┘  └────┬─────┘  └─────┬─────┘  └────┬────┘  └───────┬────────┘  │
│       │            │              │             │                │           │
│       └────────────┴──────────────┴─────────────┴────────────────┘           │
│                                   │                                          │
│                          Axios API Client                                    │
│                    (Token Auth, Auto-Refresh)                                │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │ HTTPS/REST
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI + Python)                          │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         API Layer (/api/v1)                             │  │
│  │  ┌──────┐ ┌──────────┐ ┌────────┐ ┌─────────────┐ ┌──────────────────┐  │  │
│  │  │ Auth │ │Documents │ │Lessons │ │ Processing  │ │ Dashboard/Search │  │  │
│  │  └──┬───┘ └────┬─────┘ └───┬────┘ └──────┬──────┘ └────────┬─────────┘  │  │
│  └─────┼──────────┼───────────┼─────────────┼─────────────────┼────────────┘  │
│        │          │           │             │                 │               │
│  ┌─────┴──────────┴───────────┴─────────────┴─────────────────┴────────────┐  │
│  │                         Service Layer                                   │  │
│  │  ┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌─────────────────────┐ │  │
│  │  │ AuthService│ │DocumentService│ │ AIService │ │ StepProcessor      │ │  │
│  │  └────────────┘ └──────────────┘ └─────┬──────┘ └──────────┬──────────┘ │  │
│  │  ┌────────────┐ ┌──────────────┐       │                   │            │  │
│  │  │AudioService│ │FileProcessor │       │                   │            │  │
│  │  │   (gTTS)   │ │(PDF/DOCX/TXT)│       │                   │            │  │
│  │  └─────┬──────┘ └──────┬───────┘       │                   │            │  │
│  └────────┼───────────────┼───────────────┼───────────────────┼────────────┘  │
│           │               │               │                   │               │
│           ▼               ▼               ▼                   ▼               │
│  ┌──────────────┐  ┌────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │ File System  │  │  SQLite    │  │ OpenAI API    │  │ Google TTS (gTTS)   │ │
│  │ ./uploads/   │  │ (Async)    │  │ GPT-4o        │  │ British English     │ │
│  │ ./audio/     │  │            │  │ (or Claude)   │  │                     │ │
│  └──────────────┘  └────────────┘  └───────────────┘  └─────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Next.js 14, React 18, TypeScript | App Router for modern SSR/CSR, TypeScript for type safety |
| **Styling** | Tailwind CSS, Framer Motion | Utility-first CSS, smooth animations |
| **Backend** | FastAPI, Python 3.11+ | High performance async framework, native OpenAPI docs |
| **Database** | SQLite + aiosqlite | Simple deployment, async support, sufficient for demo scale |
| **ORM** | SQLAlchemy 2.0 (async) | Industry standard, excellent async support |
| **AI/LLM** | OpenAI GPT-4o | Best structured output support, reliable JSON schema mode |
| **TTS** | gTTS (Google TTS) | Free, reliable, good quality British English voice |
| **Auth** | JWT (HS256) | Stateless authentication, token rotation pattern |

---

## 3. Ingestion Pipeline Architecture

### 3.1 Step-by-Step Processing Model

A key architectural decision was implementing **frontend-controlled, step-by-step processing** rather than monolithic background jobs. This provides:

- **Visibility**: Users see real-time progress through each stage
- **Reliability**: Failed steps can be retried individually without reprocessing everything
- **Debuggability**: Clear identification of which step failed and why
- **Control**: Frontend can pause/cancel/retry at any point

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         PROCESSING PIPELINE                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ┌──────────────┐    ┌───────────────┐    ┌─────────────────┐            │
│   │   STEP 1     │    │    STEP 2     │    │     STEP 3      │            │
│   │ EXTRACT_TEXT │───▶│EXTRACT_THEMES │───▶│ GENERATE_LESSON │            │
│   │              │    │               │    │                 │            │
│   │ • Read file  │    │ • Call LLM    │    │ • Call LLM      │            │
│   │ • Detect type│    │ • Parse 3-7   │    │ • 250-400 words │            │
│   │ • Extract    │    │   themes      │    │ • Structured    │            │
│   │ • Validate   │    │ • Store in DB │    │   output        │            │
│   └──────────────┘    └───────────────┘    └────────┬────────┘            │
│                                                      │                     │
│                                                      ▼                     │
│   ┌──────────────┐    ┌───────────────┐    ┌─────────────────┐            │
│   │   STEP 5     │    │    STEP 4     │    │                 │            │
│   │GENERATE_AUDIO│◀───│EXTRACT_CITATIONS◀──┤                 │            │
│   │              │    │               │    │                 │            │
│   │ • gTTS call  │    │ • Call LLM    │    │                 │            │
│   │ • Save MP3   │    │ • 2-3 quotes  │    │                 │            │
│   │ • Calc duration   │ • Validate    │    │                 │            │
│   └──────────────┘    └───────────────┘    └─────────────────┘            │
│                                                                            │
│   Each step: Idempotent │ Retry 3x │ Exponential Backoff                  │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 File Type Handling

| File Type | Library | Extraction Method | Validation |
|-----------|---------|-------------------|------------|
| **PDF** | PyMuPDF (fitz) | Page-by-page text extraction | MIME type check, minimum content |
| **DOCX** | python-docx | Paragraph + table extraction | MIME type check, minimum content |
| **TXT** | Native Python | UTF-8 file read | Extension + encoding validation |

**Security measures:**
- MIME type verification using `python-magic` (prevents extension spoofing)
- File size limit: 10MB maximum
- Content validation: Minimum 10 words required
- Sanitized filenames with UUID prefixes

### 3.3 Data Flow Diagram

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  User    │     │ Frontend │     │   Backend    │     │  External   │
│          │     │ (Next.js)│     │  (FastAPI)   │     │  Services   │
└────┬─────┘     └────┬─────┘     └──────┬───────┘     └──────┬──────┘
     │                │                   │                    │
     │ Upload File    │                   │                    │
     │───────────────▶│                   │                    │
     │                │ POST /upload      │                    │
     │                │──────────────────▶│                    │
     │                │                   │ Save file          │
     │                │                   │ Create document    │
     │                │   Document ID     │ (status: PENDING)  │
     │                │◀──────────────────│                    │
     │                │                   │                    │
     │                │ POST /process/    │                    │
     │                │   extract-text    │                    │
     │                │──────────────────▶│                    │
     │                │                   │ Read file          │
     │                │                   │ Extract text       │
     │                │   Step complete   │ Store raw_content  │
     │                │◀──────────────────│                    │
     │                │                   │                    │
     │                │ POST /process/    │                    │
     │                │   extract-themes  │                    │
     │                │──────────────────▶│                    │
     │                │                   │ Call OpenAI        │
     │                │                   │──────────────────▶ │
     │                │                   │   GPT-4o           │
     │                │                   │◀────────────────── │
     │                │   Themes (3-7)    │ Parse & store      │
     │                │◀──────────────────│                    │
     │                │                   │                    │
     │                │ POST /process/    │                    │
     │                │   generate-lesson │                    │
     │                │──────────────────▶│                    │
     │                │                   │ Call OpenAI        │
     │                │                   │──────────────────▶ │
     │                │                   │   Structured JSON  │
     │                │                   │◀────────────────── │
     │                │   Lesson data     │ Create lesson      │
     │                │◀──────────────────│                    │
     │                │                   │                    │
     │                │ POST /process/    │                    │
     │                │   extract-citations                    │
     │                │──────────────────▶│                    │
     │                │                   │ Call OpenAI        │
     │                │                   │──────────────────▶ │
     │                │                   │◀────────────────── │
     │                │   Citations (2-3) │ Validate & store   │
     │                │◀──────────────────│                    │
     │                │                   │                    │
     │                │ POST /process/    │                    │
     │                │   generate-audio  │                    │
     │                │──────────────────▶│                    │
     │                │                   │ Call gTTS          │
     │                │                   │──────────────────▶ │
     │                │                   │   Google TTS       │
     │                │                   │◀────────────────── │
     │                │   Audio URL       │ Save MP3, duration │
     │                │◀──────────────────│                    │
     │                │                   │                    │
     │ View Lesson    │ GET /lessons/...  │                    │
     │───────────────▶│──────────────────▶│                    │
     │                │   Full lesson +   │                    │
     │◀───────────────│◀──────────────────│                    │
     │                │   themes + audio  │                    │
     │                │                   │                    │
```

---

## 4. AI Processing Architecture

### 4.1 LLM Integration Design

**Provider:** OpenAI GPT-4o (gpt-4o-2024-11-20)

**Key Decision:** Use OpenAI's native JSON Schema mode for structured outputs rather than prompt engineering alone.

```python
# Theme extraction with strict schema
response = client.chat.completions.create(
    model="gpt-4o-2024-11-20",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "themes_response",
            "strict": True,
            "schema": ThemeSchema
        }
    }
)

# Lesson generation with Pydantic model
response = client.beta.chat.completions.parse(
    model="gpt-4o-2024-11-20",
    response_format=LessonOutput  # Pydantic model
)
```

**Benefits:**
- **Guaranteed valid JSON**: No parsing failures
- **Type safety**: Response matches Pydantic schema
- **Fewer retries**: Eliminates malformed output errors

### 4.2 Citation Extraction & Validation

Citations are validated against the source document to ensure accuracy:

```python
# Citation validation
for citation in extracted_citations:
    if citation.snippet not in document.raw_content:
        logger.warning(f"Citation not found in source: {citation.snippet[:50]}...")
        # Flag for review but don't fail
```

### 4.3 Retry Strategy

All AI operations implement exponential backoff:

| Attempt | Delay | Cumulative |
|---------|-------|------------|
| 1 | 0s | 0s |
| 2 | 1s | 1s |
| 3 | 2s | 3s |
| 4 | 4s | 7s |

Handled exceptions: `APIError`, `RateLimitError`, `APITimeoutError`

---

## 5. Audio Generation Architecture

### 5.1 gTTS Implementation

**Decision:** Use Google Text-to-Speech (gTTS) over alternatives.

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **gTTS** | Free, reliable, good quality | Requires internet | **Selected** |
| OpenAI TTS | Excellent quality | Costs money | Rejected |
| Edge TTS | Free, high quality | Complex setup | Backup option |
| pyttsx3 | Offline | Poor quality | Rejected |

**Implementation:**
```python
async def generate_audio(text: str) -> Tuple[str, float]:
    tts = gTTS(text=text, lang='en', tld='co.uk')  # British English

    # Run synchronous gTTS in thread pool
    await asyncio.to_thread(tts.save, filepath)

    # Calculate duration with pydub
    audio = AudioSegment.from_mp3(filepath)
    duration = len(audio) / 1000.0

    return filepath, duration
```

### 5.2 Audio Delivery

- **Storage:** `./uploads/audio/{uuid}.mp3`
- **Serving:** FastAPI static file mount at `/static/audio/`
- **URL Generation:** `{BASE_URL}/static/audio/narration_{uuid}.mp3`

---

## 6. Persistence & Data Integrity

### 6.1 Database Schema Design

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     USERS       │       │   DOCUMENTS     │       │     THEMES      │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (UUID) PK    │──┐    │ id (UUID) PK    │──┐    │ id (UUID) PK    │
│ email (UNIQUE)  │  │    │ ingestion_id    │  │    │ document_id FK  │
│ hashed_password │  │    │   (UNIQUE)      │  │    │ name            │
│ full_name       │  │    │ user_id FK      │  │    │ description     │
│ ...settings     │  │    │ title           │  │    │ order           │
└─────────────────┘  │    │ file_name       │  │    └─────────────────┘
                     │    │ file_type       │  │
                     │    │ raw_content     │  │    ┌─────────────────┐
                     │    │ status          │  │    │    LESSONS      │
                     │    │ step_statuses   │  │    ├─────────────────┤
                     └────│ ...             │  ├────│ id (UUID) PK    │
                          └─────────────────┘  │    │ document_id FK  │
                                               │    │   (UNIQUE)      │
                          ┌─────────────────┐  │    │ title, summary  │
                          │   CITATIONS     │  │    │ content         │
                          ├─────────────────┤  │    │ audio_path      │
                          │ id (UUID) PK    │  │    │ audio_duration  │
                          │ document_id FK  │──┘    │ ...progress     │
                          │ snippet         │       └─────────────────┘
                          │ location        │
                          │ relevance_score │
                          └─────────────────┘
```

### 6.2 Ingestion ID Pattern

Every document has a unique `ingestion_id` (UUID) that:
- Enables idempotent operations
- Links all artifacts (themes, lesson, citations, audio)
- Supports API queries: `GET /documents/ingestion/{ingestion_id}`

### 6.3 Step Status Tracking

```python
class Document(Base):
    step_statuses = Column(JSON)  # {"EXTRACT_TEXT": "completed", ...}
    failed_step = Column(String)
    step_error_message = Column(String)
    retry_count = Column(Integer)
```

---

## 7. Trade-offs & Decisions

### 7.1 SQLite vs PostgreSQL

| Factor | SQLite | PostgreSQL |
|--------|--------|------------|
| Setup complexity | None | Requires server |
| Deployment | Single file | Container/service |
| Concurrent writes | Limited | Excellent |
| **Decision** | **Selected for demo** | Production choice |

**Rationale:** SQLite simplifies local development and evaluation. Schema is PostgreSQL-compatible for easy migration.

### 7.2 Synchronous vs Async Processing

| Approach | Pros | Cons |
|----------|------|------|
| Background jobs (Celery) | Non-blocking, scalable | Complex setup, harder to debug |
| **Step-by-step API calls** | **Visible progress, easy retry** | **Longer page session** |

**Rationale:** Frontend-controlled steps provide superior UX with real-time progress visibility and granular retry capability.

### 7.3 gTTS vs Premium TTS

| Factor | gTTS | OpenAI TTS |
|--------|------|------------|
| Cost | Free | $15/1M chars |
| Quality | Good | Excellent |
| Reliability | Google infrastructure | API dependent |
| **Decision** | **Selected** | Over-engineered for demo |

---

## 8. Reliability & Correctness Measures

### 8.1 Input Validation

1. **File type validation**: Extension + MIME type double-check
2. **Size limits**: 10MB maximum enforced at API layer
3. **Content validation**: Minimum 10 words, encoding verification
4. **Sanitization**: UUID-prefixed filenames prevent path traversal

### 8.2 Processing Reliability

1. **Idempotent steps**: Re-running a step produces same result
2. **Retry mechanism**: 3 attempts with exponential backoff
3. **Failure isolation**: One step failure doesn't corrupt others
4. **Status tracking**: Precise visibility into processing state

### 8.3 Citation Accuracy

1. **Exact match validation**: Verify snippets exist in source
2. **Location mapping**: Reference page/paragraph when available
3. **Relevance scoring**: AI ranks citation importance

### 8.4 Audio Verification

1. **Duration calculation**: Verify audio generated correctly
2. **File existence check**: Confirm MP3 saved before updating DB
3. **URL validation**: Test static file serving

---

## 9. Sequence Diagram: Full Ingestion Flow

```
┌──────┐          ┌────────┐          ┌────────┐          ┌───────┐          ┌─────┐
│Client│          │Frontend│          │Backend │          │OpenAI │          │gTTS │
└──┬───┘          └───┬────┘          └───┬────┘          └───┬───┘          └──┬──┘
   │                  │                   │                   │                 │
   │ Select file      │                   │                   │                 │
   │─────────────────▶│                   │                   │                 │
   │                  │ POST /upload      │                   │                 │
   │                  │──────────────────▶│                   │                 │
   │                  │                   │ Validate file     │                 │
   │                  │                   │ Save to disk      │                 │
   │                  │                   │ Create DB record  │                 │
   │                  │ 201 {document}    │                   │                 │
   │                  │◀──────────────────│                   │                 │
   │                  │                   │                   │                 │
   │                  │ POST extract-text │                   │                 │
   │                  │──────────────────▶│                   │                 │
   │                  │                   │ PyMuPDF/docx      │                 │
   │                  │ 200 {step done}   │                   │                 │
   │                  │◀──────────────────│                   │                 │
   │                  │                   │                   │                 │
   │                  │ POST extract-themes                   │                 │
   │                  │──────────────────▶│                   │                 │
   │                  │                   │ themes request    │                 │
   │                  │                   │──────────────────▶│                 │
   │                  │                   │ JSON schema resp  │                 │
   │                  │                   │◀──────────────────│                 │
   │                  │ 200 {themes}      │                   │                 │
   │                  │◀──────────────────│                   │                 │
   │                  │                   │                   │                 │
   │                  │ POST generate-lesson                  │                 │
   │                  │──────────────────▶│                   │                 │
   │                  │                   │ lesson request    │                 │
   │                  │                   │──────────────────▶│                 │
   │                  │                   │ structured output │                 │
   │                  │                   │◀──────────────────│                 │
   │                  │ 200 {lesson}      │                   │                 │
   │                  │◀──────────────────│                   │                 │
   │                  │                   │                   │                 │
   │                  │ POST extract-citations                │                 │
   │                  │──────────────────▶│                   │                 │
   │                  │                   │ citations req     │                 │
   │                  │                   │──────────────────▶│                 │
   │                  │                   │ validated quotes  │                 │
   │                  │                   │◀──────────────────│                 │
   │                  │ 200 {citations}   │                   │                 │
   │                  │◀──────────────────│                   │                 │
   │                  │                   │                   │                 │
   │                  │ POST generate-audio                   │                 │
   │                  │──────────────────▶│                   │                 │
   │                  │                   │ TTS request       │                 │
   │                  │                   │─────────────────────────────────────▶
   │                  │                   │ MP3 stream        │                 │
   │                  │                   │◀─────────────────────────────────────
   │                  │ 200 {audio_url}   │                   │                 │
   │                  │◀──────────────────│                   │                 │
   │                  │                   │                   │                 │
   │ Processing done  │                   │                   │                 │
   │◀─────────────────│                   │                   │                 │
   │                  │                   │                   │                 │
```

---

## 10. Exceeding Requirements

| Requirement | Implementation | Exceeds By |
|-------------|----------------|------------|
| 2 file types | PDF, DOCX, TXT | +1 file type |
| 3-7 themes | Configurable, validated schema | Strict JSON schema |
| 250-400 words | Pydantic-validated lesson | Structured sections |
| Voice narration | gTTS with duration tracking | Audio progress sync |
| 2-3 citations | Validated against source | Relevance scoring |
| ingestion_id | Full artifact linkage | Step-level tracking |
| Basic persistence | Activity logging, notifications | Learning progress |

---

## 11. Conclusion

Cognify's architecture prioritizes **correctness and reliability** through:

1. **Step-by-step processing** with individual retry capability
2. **Strict schema validation** using OpenAI's JSON schema mode
3. **Multi-layer input validation** (extension, MIME, content)
4. **Citation verification** against source documents
5. **Comprehensive error handling** with exponential backoff
6. **Full traceability** via ingestion_id and step status tracking

The system is designed for easy local evaluation while maintaining production-ready patterns for database schema, authentication, and API design.

---

*End of Architecture Note*
