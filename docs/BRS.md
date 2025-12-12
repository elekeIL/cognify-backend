# Cognify - Business Requirements Specification (BRS)

## 1. Project Overview

**Product Name:** Cognify
**Purpose:** AI-powered learning content generation platform for workplace upskilling

## 2. User Goals

### Primary User: Corporate Learning Administrator
- **Goal:** Transform existing training materials into engaging, bite-sized lessons
- **Pain Point:** Manual content curation is time-consuming and inconsistent
- **Value Proposition:** Automated extraction of key themes and generation of structured lessons

### Secondary User: Employee/Learner
- **Goal:** Quickly understand complex documents through concise lessons
- **Pain Point:** Information overload from lengthy documents
- **Value Proposition:** Focused 250-400 word lessons with audio narration

## 3. Business Outcomes

| Outcome | Metric | Target |
|---------|--------|--------|
| Content Creation Speed | Time to create lesson | < 60 seconds |
| Learning Engagement | Audio completion rate | > 70% |
| Content Quality | Theme accuracy | > 90% relevance |
| User Adoption | Documents uploaded per user/week | > 3 |

## 4. Functional Requirements

### Core Features (Must Have)

| ID | Feature | Description |
|----|---------|-------------|
| F1 | Document Upload | Support PDF, DOCX, TXT files up to 10MB |
| F2 | Theme Extraction | AI identifies 3-7 main themes |
| F3 | Lesson Generation | 250-400 word workplace-focused lesson |
| F4 | Voice Narration | British-accented audio narration |
| F5 | Citation Extraction | Top 2-3 source snippets with location |
| F6 | Progress Tracking | Track lesson completion and time spent |

### Supporting Features (Should Have)

| ID | Feature | Description |
|----|---------|-------------|
| S1 | User Authentication | Secure login with JWT tokens |
| S2 | Dashboard | Overview of documents, lessons, progress |
| S3 | Search | Find documents and lessons by keyword |
| S4 | Activity History | Timeline of user actions |
| S5 | Notifications | Alerts for processing completion/failure |

## 5. Constraints

### Technical Constraints
- API response time < 5 seconds for non-AI operations
- AI processing < 60 seconds total per document
- File size limit: 10MB
- Supported formats: PDF, DOCX, TXT only

### Business Constraints
- OpenAI API costs must be managed (GPT-4o usage)
- gTTS for audio (free tier, no commercial restrictions)
- Single-tenant architecture for MVP

### Regulatory Constraints
- No PII storage beyond user authentication
- Document content stored but not shared between users

## 6. Success Criteria

### Acceptance Criteria

1. **Document Ingestion**
   - [x] Upload works for PDF, DOCX, and TXT
   - [x] Invalid files are rejected with clear error message
   - [x] Word count is calculated and displayed

2. **AI Processing**
   - [x] Themes are coherent and grounded in source
   - [x] Lesson is concise, workplace-relevant, and matches themes
   - [x] Citations include exact quotes with locations

3. **Audio Narration**
   - [x] Audio plays reliably in browser
   - [x] Audio matches lesson text
   - [x] British accent is clear and professional

4. **Data Persistence**
   - [x] Data persists across sessions
   - [x] Retrievable by ingestion_id
   - [x] Delete removes all associated data

5. **User Experience**
   - [x] Clean, responsive UI
   - [x] Progress visible during processing
   - [x] Error states are clearly communicated

## 7. Out of Scope (Future Enhancements)

- Multi-language support
- Custom voice selection
- Collaborative features
- API rate limiting per user
- Advanced analytics dashboard
- Mobile application
