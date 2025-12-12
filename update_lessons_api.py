#!/usr/bin/env python3
"""Script to update lessons API to return paginated response with themes."""

import re

# Read the file
with open('app/api/routes/lessons.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports for ThemeResponse and LessonListResponse
old_imports = """from app.schemas.lesson import (
    LessonResponse,
    LessonWithAudioResponse,
    LessonProgressUpdate,
    LessonOutcomeUpdate,
    LessonListResponse,
)"""

new_imports = """from app.schemas.lesson import (
    LessonResponse,
    LessonWithAudioResponse,
    LessonProgressUpdate,
    LessonOutcomeUpdate,
    LessonListResponse,
)
from app.schemas.theme import ThemeResponse"""

content = content.replace(old_imports, new_imports)

# If the old imports don't have LessonListResponse, try without it
if 'from app.schemas.theme import ThemeResponse' not in content:
    old_imports2 = """from app.schemas.lesson import (
    LessonResponse,
    LessonWithAudioResponse,
    LessonProgressUpdate,
    LessonOutcomeUpdate,
)"""

    new_imports2 = """from app.schemas.lesson import (
    LessonResponse,
    LessonWithAudioResponse,
    LessonProgressUpdate,
    LessonOutcomeUpdate,
    LessonListResponse,
)
from app.schemas.theme import ThemeResponse"""

    content = content.replace(old_imports2, new_imports2)

# 2. Replace the list_lessons function
old_list_function = '''@router.get("", response_model=list[LessonWithAudioResponse])
async def list_lessons(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 10,
):
    """
    List all completed lessons for the current user.

    Only returns lessons from successfully processed documents.
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    query = (
        select(Lesson)
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Document.status == DocumentStatus.COMPLETED)
        .order_by(Lesson.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    lessons = result.scalars().all()

    return [
        LessonWithAudioResponse(
            id=lesson.id,
            document_id=lesson.document_id,
            title=lesson.title,
            summary=lesson.summary,
            content=lesson.content,
            word_count=lesson.word_count,
            what_youll_learn=lesson.what_youll_learn,
            key_takeaways=lesson.key_takeaways,
            apply_at_work=lesson.apply_at_work,
            audio_path=lesson.audio_path,
            audio_duration=lesson.audio_duration,
            audio_url=audio_service.get_audio_url(lesson.audio_path),
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )
        for lesson in lessons
    ]'''

new_list_function = '''@router.get("", response_model=LessonListResponse)
async def list_lessons(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 10,
):
    """
    List all lessons for the current user with pagination.

    Returns lessons from successfully processed documents with themes.
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    # Count total lessons
    count_query = (
        select(func.count(Lesson.id))
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Document.status == DocumentStatus.COMPLETED)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated lessons with document relationship for themes
    query = (
        select(Lesson)
        .join(Document)
        .where(Document.user_id == current_user.id)
        .where(Document.status == DocumentStatus.COMPLETED)
        .order_by(Lesson.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    lessons = result.scalars().all()

    # Build response items
    items = []
    for lesson in lessons:
        # Fetch document with themes for this lesson
        doc_query = select(Document).where(Document.id == lesson.document_id)
        doc_result = await db.execute(doc_query)
        document = doc_result.scalar_one_or_none()

        items.append(LessonWithAudioResponse(
            id=lesson.id,
            document_id=lesson.document_id,
            title=lesson.title,
            summary=lesson.summary,
            content=lesson.content,
            word_count=lesson.word_count,
            what_youll_learn=lesson.what_youll_learn,
            key_takeaways=lesson.key_takeaways,
            apply_at_work=lesson.apply_at_work,
            learning_outcomes=lesson.learning_outcomes,
            audio_path=lesson.audio_path,
            audio_duration=lesson.audio_duration,
            audio_url=audio_service.get_audio_url(lesson.audio_path),
            is_completed=lesson.is_completed,
            progress_percentage=lesson.progress_percentage,
            audio_position=lesson.audio_position,
            time_spent_seconds=lesson.time_spent_seconds,
            outcomes_completed=lesson.outcomes_completed,
            completed_at=lesson.completed_at,
            last_accessed_at=lesson.last_accessed_at,
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        ))

    return LessonListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )'''

content = content.replace(old_list_function, new_list_function)

# Write the updated file
with open('app/api/routes/lessons.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated app/api/routes/lessons.py successfully!")
