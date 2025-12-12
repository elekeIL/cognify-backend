# Cognify - Presentation Slide Deck

**Technical Interview Presentation**
**December 2024**

---

## Slide 1: The Problem

### Title: The Knowledge Transfer Gap

**Pain Points:**
- Employees receive lengthy documents but lack time to read them thoroughly
- Traditional training content creation is slow and inconsistent
- Information overload leads to poor knowledge retention
- No audio option for passive/multitasking learning

**Market Reality:**
- Average employee spends 2.5 hours/day searching for information (McKinsey)
- 70% of knowledge workers feel overwhelmed by information volume
- Only 12% of employees apply what they learn in training (Harvard)

**The Challenge:**
> Transform arbitrary documents into engaging, structured lessons that employees can consume in 2-3 minutes—with voice narration and clear workplace applications.

---

## Slide 2: Our Approach

### Title: AI-Powered Learning Transformation

**Core Solution:**
```
Document Upload → AI Analysis → Structured Lesson → Audio Narration
```

**Key Differentiators:**

| Feature | Traditional | Cognify |
|---------|------------|---------|
| Content creation | Hours/days | <90 seconds |
| Format | Static text | Interactive + audio |
| Structure | Manual curation | AI-structured sections |
| Learning outcomes | Generic | Document-specific |

**Design Principles:**
1. **Workplace Focus** - "Apply at Work" section in every lesson
2. **Bite-sized** - 250-400 words (2-3 min read/listen)
3. **Verifiable** - Source citations with exact quotes
4. **Trackable** - Progress, outcomes, time spent

**User Flow:**
```
Upload PDF/DOCX/TXT → Watch 5-step AI processing →
Learn with text + audio → Track completion
```

---

## Slide 3: Architecture

### Title: System Design & Pipeline

**High-Level Architecture:**
```
┌────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                   │
│   Dashboard │ Upload │ Documents │ Learning │ History      │
└──────────────────────────┬─────────────────────────────────┘
                           │ REST API (Axios)
                           ▼
┌────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Step-by-Step Processing                  │  │
│  │  EXTRACT   →  EXTRACT  →  GENERATE  →  EXTRACT  →    │  │
│  │   TEXT       THEMES       LESSON     CITATIONS       │  │
│  │                                           ↓          │  │
│  │                                      GENERATE        │  │
│  │                                       AUDIO          │  │
│  └──────────────────────────────────────────────────────┘  │
└──────┬────────────────┬───────────────────┬────────────────┘
       │                │                   │
       ▼                ▼                   ▼
   SQLite          OpenAI GPT-4o        gTTS (Google)
   (async)         Structured Output     British English
```

**Processing Pipeline:**

| Step | Technology | Output |
|------|------------|--------|
| 1. Extract Text | PyMuPDF/python-docx | Raw content |
| 2. Extract Themes | GPT-4o (JSON Schema) | 3-7 themes |
| 3. Generate Lesson | GPT-4o (Pydantic) | Structured lesson |
| 4. Extract Citations | GPT-4o | 2-3 validated quotes |
| 5. Generate Audio | gTTS | MP3 narration |

**Key Design Decisions:**
- Frontend-controlled steps (vs. background queue)
- Idempotent operations with ingestion_id
- Retry mechanism: 3 attempts with exponential backoff

---

## Slide 4: Technology Stack

### Title: Stack & Implementation Details

**Backend:**
| Component | Technology | Why |
|-----------|------------|-----|
| Framework | FastAPI | Async performance, OpenAPI docs |
| Database | SQLite + aiosqlite | Zero-config, async support |
| ORM | SQLAlchemy 2.0 | Industry standard, PostgreSQL-ready |
| Auth | JWT (python-jose) | Stateless, token rotation |

**AI/Processing:**
| Component | Technology | Why |
|-----------|------------|-----|
| LLM | OpenAI GPT-4o | Best structured output support |
| TTS | gTTS | Free, reliable, quality voice |
| PDF | PyMuPDF (fitz) | Fast, accurate extraction |
| DOCX | python-docx | Tables + paragraphs support |

**Frontend:**
| Component | Technology | Why |
|-----------|------------|-----|
| Framework | Next.js 14 | App Router, SSR/CSR |
| Styling | Tailwind CSS | Utility-first, rapid development |
| State | React Context | Simple, sufficient for scope |
| Animation | Framer Motion | Smooth, professional UX |

**Exceeding Requirements:**
- ✅ 3 file types (PDF, DOCX, TXT) - requirement was 2
- ✅ Learning outcomes with auto-completion via audio
- ✅ Full activity history and notifications
- ✅ Multi-language UI (EN, ES, FR, DE)
- ✅ Dark mode support

---

## Slide 5: Risks & Roadmap

### Title: Known Limitations & Future Direction

**Current Risks & Mitigations:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenAI rate limits | Processing delays | Exponential backoff, 3 retries |
| gTTS network dependency | Audio generation fails | Retry logic, fallback to edge-tts |
| SQLite write contention | Concurrent user issues | PostgreSQL migration path ready |
| Large document processing | Timeout/truncation | Content truncated to 12K chars |

**Security Considerations:**
- MIME type validation prevents extension spoofing
- User data isolation (all queries filtered by user_id)
- JWT tokens with 30-min expiration
- bcrypt password hashing

**Roadmap (Post-MVP):**

| Phase | Features | Timeline |
|-------|----------|----------|
| **v1.1** | Premium TTS voices, quiz generation | +2 weeks |
| **v1.2** | PostgreSQL, S3 storage, deployment | +2 weeks |
| **v2.0** | Multi-language lessons, collaboration | +4 weeks |
| **v3.0** | Analytics dashboard, API access | +6 weeks |

**Scalability Path:**
```
Current (SQLite) → PostgreSQL → Read replicas → Microservices
```

**Demo-Ready Highlights:**
- Full end-to-end processing works reliably
- Real-time progress visibility
- Professional "for-work" content structure
- Audio plays seamlessly in browser

---

## Appendix: Evaluation Criteria Mapping

| Criterion (Weight) | How Cognify Addresses It |
|-------------------|--------------------------|
| **Product thinking & UX (20%)** | Dashboard, progress tracking, "Apply at Work" sections, audio player |
| **Correctness & reliability (25%)** | Step-by-step retry, citation validation, MIME checking, idempotent ops |
| **Code quality & tests (20%)** | Service layer pattern, Pydantic schemas, TypeScript frontend |
| **Architecture & trade-offs (20%)** | Documented decisions, scalability path, clean separation of concerns |
| **Docs & presentation (15%)** | Complete Architecture Note, BRS, FRS, this slide deck |

---

*End of Slide Deck*
