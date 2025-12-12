"""AI service for accurate theme extraction, citation finding, and lesson generation."""

import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Literal

from pydantic import BaseModel, Field
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from anthropic import AsyncAnthropic, APIError as AnthropicAPIError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds

settings = get_settings()


# =============================================
# Pydantic Models → Enforce 100% correct structure
# =============================================

class Theme(BaseModel):
    name: str = Field(..., description="Concise theme name (2–4 words)", max_length=30)
    description: str = Field(..., description="1–2 sentence explanation of the theme")


class LearningOutcome(BaseModel):
    id: str = Field(..., pattern=r"^lo\d+$", examples=["lo1", "lo2"])
    title: str = Field(..., description="Short action phrase starting with a verb")
    description: str = Field(..., description="One sentence explaining mastery")


class LessonOutput(BaseModel):
    title: str = Field(..., description="Engaging lesson title")
    summary: str = Field(..., description="2–3 sentence overview")
    content: str = Field(..., description="Main lesson body (~300 words)")
    what_youll_learn: str = Field(..., description="What the reader will gain")
    key_takeaways: List[str] = Field(..., min_items=3, max_items=5)
    apply_at_work: str = Field(..., description="Practical workplace applications")
    learning_outcomes: List[LearningOutcome] = Field(..., min_items=4, max_items=6)


class Citation(BaseModel):
    snippet: str = Field(..., description="Exact quote from document (2–4 sentences)")
    location: Literal[
        "Beginning", "Early section", "Middle", "Late section", "End", "Throughout"
    ]
    relevance: str = Field(..., description="Which theme(s) this supports")


class AIService:
    """High-accuracy AI service using structured outputs (2025 best practices)."""

    def __init__(self):
        self.provider = settings.llm_provider.lower()

        if self.provider == "openai":
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=60.0,  # 60 second timeout
            )
        elif self.provider == "anthropic":
            self.client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=60.0,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    # =============================================
    # 1. Extract Themes — 100% Accurate JSON
    # =============================================
    async def extract_themes(self, content: str, num_themes: int = 5) -> List[Theme]:
        num_themes = max(3, min(7, num_themes))
        original_length = len(content)
        truncated = content[:12000]  # GPT-4o supports up to 128k, safe limit

        if original_length > 12000:
            logger.info(f"Content truncated for theme extraction: {original_length} -> 12000 chars ({(12000/original_length)*100:.1f}% of original)")

        return await self._extract_themes_with_retry(truncated, num_themes)

    async def _extract_themes_with_retry(self, truncated: str, num_themes: int) -> List[Theme]:
        """Extract themes with retry logic."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._extract_themes_impl(truncated, num_themes)
            except (APIError, RateLimitError, APITimeoutError, AnthropicAPIError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"Theme extraction failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Theme extraction failed after {MAX_RETRIES} attempts: {e}")
        raise last_error

    async def _extract_themes_impl(self, truncated: str, num_themes: int) -> List[Theme]:
        """Actual theme extraction implementation."""
        if self.provider == "openai":
            response = await self.client.chat.completions.create(
                model="gpt-4o-2024-11-20",  # Latest structured output model
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content analyst. Extract the most important themes from workplace documents.",
                    },
                    {
                        "role": "user",
                        "content": f"Extract exactly {num_themes} main themes from this document:\n\n{truncated}",
                    },
                ],
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "themes_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "themes": {
                                    "type": "array",
                                    "items": {"$ref": "#/$defs/theme"},
                                    "minItems": num_themes,
                                    "maxItems": num_themes,
                                }
                            },
                            "required": ["themes"],
                            "additionalProperties": False,
                            "$defs": {
                                "theme": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "maxLength": 30},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["name", "description"],
                                    "additionalProperties": False,
                                }
                            },
                        },
                    },
                },
            )
            data = json.loads(response.choices[0].message.content)
            return [Theme(**t) for t in data["themes"]]

        else:  # Anthropic (still no native JSON schema, but very reliable with XML)
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Extract exactly {num_themes} main themes from this document.

Return ONLY this XML format (no extra text):

<themes>
  <theme>
    <name>Concise Theme Name</name>
    <description>One to two sentence description.</description>
  </theme>
  ...
</themes>

Document:
{truncated}"""
                    }
                ],
            )
            xml_text = response.content[0].text.strip()
            # Handle potential markdown code blocks
            if xml_text.startswith("```"):
                xml_text = xml_text.split("```")[1]
                if xml_text.startswith("xml"):
                    xml_text = xml_text[3:]
                xml_text = xml_text.strip()

            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError as e:
                logger.error(f"Failed to parse XML themes response: {e}")
                raise ValueError(f"Invalid XML response from AI: {e}")

            themes = []
            for theme_elem in root.findall("theme"):
                name_elem = theme_elem.find("name")
                desc_elem = theme_elem.find("description")
                if name_elem is not None and name_elem.text:
                    name = name_elem.text.strip()
                    desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                    themes.append(Theme(name=name, description=desc))

            if not themes:
                raise ValueError("No themes could be parsed from AI response")

            return themes

    # =============================================
    # 2. Generate Lesson — Guaranteed Structure
    # =============================================
    async def generate_lesson(
        self,
        content: str,
        themes: List[Dict[str, Any]],
        target_words: int = 325,
    ) -> LessonOutput:
        """Generate a lesson with retry logic."""
        # Handle both Theme objects and dicts
        themes_text = "\n".join([
            f"• {t.get('name') if isinstance(t, dict) else t.name}: {t.get('description', '') if isinstance(t, dict) else t.description}"
            for t in themes
        ])
        original_length = len(content)
        truncated = content[:10000]

        if original_length > 10000:
            logger.info(f"Content truncated for lesson generation: {original_length} -> 10000 chars ({(10000/original_length)*100:.1f}% of original)")

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._generate_lesson_impl(truncated, themes_text, target_words)
            except (APIError, RateLimitError, APITimeoutError, AnthropicAPIError, ValueError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"Lesson generation failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Lesson generation failed after {MAX_RETRIES} attempts: {e}")
        raise last_error

    async def _generate_lesson_impl(self, truncated: str, themes_text: str, target_words: int) -> LessonOutput:
        """Actual lesson generation implementation."""
        prompt = f"""Create a professional workplace learning lesson based on this document and its key themes.

Document excerpt:
{truncated}

Key themes:
{themes_text}

Target word count for main content: ~{target_words} words.
Tone: Professional, approachable, practical."""

        if self.provider == "openai":
            response = await self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-11-20",
                messages=[
                    {"role": "system", "content": "You are an expert workplace instructional designer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                response_format=LessonOutput,
            )
            return response.choices[0].message.parsed

        else:  # Anthropic fallback (still excellent)
            schema_str = json.dumps(LessonOutput.model_json_schema())
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt + f"\n\nReturn your response as valid JSON matching this exact Pydantic structure (no markdown, no code blocks): {schema_str}",
                    }
                ],
            )
            # Clean response - remove any markdown code blocks if present
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            return LessonOutput.model_validate_json(response_text)

    # =============================================
    # 3. Extract Citations — Precise & Verifiable
    # =============================================
    async def extract_citations(
        self,
        content: str,
        themes: List[Dict[str, Any]],
        num_citations: int = 3,
    ) -> List[Citation]:
        """Extract citations with retry logic."""
        # Handle both Theme objects and dicts
        themes_list = ", ".join([
            t.get('name') if isinstance(t, dict) else t.name
            for t in themes
        ])
        original_length = len(content)
        truncated = content[:12000]

        if original_length > 12000:
            logger.info(f"Content truncated for citation extraction: {original_length} -> 12000 chars ({(12000/original_length)*100:.1f}% of original)")

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                citations = await self._extract_citations_impl(truncated, themes_list, num_citations)
                # Verify citations exist in source content
                verified_citations = self._verify_citations(citations, content)
                if len(verified_citations) < len(citations):
                    logger.warning(f"Citation verification: {len(citations) - len(verified_citations)} citations could not be verified in source")
                return verified_citations
            except (APIError, RateLimitError, APITimeoutError, AnthropicAPIError, ValueError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"Citation extraction failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Citation extraction failed after {MAX_RETRIES} attempts: {e}")
        raise last_error

    async def _extract_citations_impl(self, truncated: str, themes_list: str, num_citations: int) -> List[Citation]:
        """Actual citation extraction implementation."""
        if self.provider == "openai":
            response = await self.client.chat.completions.create(
                model="gpt-4o-2024-11-20",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract the most relevant direct quotes that support the given themes.",
                    },
                    {
                        "role": "user",
                        "content": f"Themes: {themes_list}\n\nDocument:\n{truncated}\n\nExtract {num_citations} best supporting quotes.",
                    },
                ],
                temperature=0.1,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "citations",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "citations": {
                                    "type": "array",
                                    "items": {"$ref": "#/$defs/citation"},
                                }
                            },
                            "required": ["citations"],
                            "additionalProperties": False,
                            "$defs": {
                                "citation": {
                                    "type": "object",
                                    "properties": {
                                        "snippet": {"type": "string"},
                                        "location": {"type": "string", "enum": ["Beginning", "Early section", "Middle", "Late section", "End", "Throughout"]},
                                        "relevance": {"type": "string"},
                                    },
                                    "required": ["snippet", "location", "relevance"],
                                    "additionalProperties": False,
                                }
                            },
                        },
                    },
                },
            )
            data = json.loads(response.choices[0].message.content)
            return [Citation(**c) for c in data["citations"]]

        else:
            # Anthropic with XML (still very reliable)
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": f"""Extract {num_citations} key quotes supporting these themes: {themes_list}

Use this exact XML format:

<citations>
  <citation>
    <snippet>Exact quote here...</snippet>
    <location>Middle</location>
    <relevance>Supports "Leadership" and "Team Trust"</relevance>
  </citation>
</citations>

Document: {truncated}"""
                }]
            )
            xml_text = response.content[0].text.strip()
            # Handle potential markdown code blocks
            if xml_text.startswith("```"):
                xml_text = xml_text.split("```")[1]
                if xml_text.startswith("xml"):
                    xml_text = xml_text[3:]
                xml_text = xml_text.strip()

            try:
                root = ET.fromstring(xml_text)
            except ET.ParseError as e:
                logger.error(f"Failed to parse XML citations response: {e}")
                raise ValueError(f"Invalid XML response from AI: {e}")

            citations = []
            for c in root.findall("citation"):
                snippet_elem = c.find("snippet")
                location_elem = c.find("location")
                relevance_elem = c.find("relevance")

                if snippet_elem is not None and snippet_elem.text:
                    snippet = snippet_elem.text.strip()
                    location = location_elem.text.strip() if location_elem is not None and location_elem.text else "Middle"
                    relevance = relevance_elem.text.strip() if relevance_elem is not None and relevance_elem.text else ""

                    # Validate location is one of the allowed values
                    valid_locations = ["Beginning", "Early section", "Middle", "Late section", "End", "Throughout"]
                    if location not in valid_locations:
                        location = "Middle"

                    citations.append(Citation(
                        snippet=snippet,
                        location=location,
                        relevance=relevance,
                    ))

            if not citations:
                raise ValueError("No citations could be parsed from AI response")

            return citations

    def _verify_citations(self, citations: List[Citation], content: str) -> List[Citation]:
        """
        Verify that citation snippets actually exist in the source content.

        Uses fuzzy matching to account for minor whitespace/formatting differences.
        Returns only citations that can be verified.
        """
        verified = []
        # Normalize content for comparison (collapse whitespace)
        normalized_content = " ".join(content.lower().split())

        for citation in citations:
            # Normalize snippet for comparison
            normalized_snippet = " ".join(citation.snippet.lower().split())

            # Check for exact match first
            if normalized_snippet in normalized_content:
                verified.append(citation)
                continue

            # Check for partial match (at least 60% of words present in sequence)
            snippet_words = normalized_snippet.split()
            if len(snippet_words) >= 3:
                # Check if at least 60% of the snippet words appear in order
                min_match_words = max(3, int(len(snippet_words) * 0.6))
                for i in range(len(snippet_words) - min_match_words + 1):
                    partial = " ".join(snippet_words[i:i + min_match_words])
                    if partial in normalized_content:
                        verified.append(citation)
                        logger.debug(f"Citation partially verified: '{citation.snippet[:50]}...'")
                        break
                else:
                    logger.warning(f"Citation could not be verified in source: '{citation.snippet[:80]}...'")
            else:
                # Very short snippets - require exact match
                logger.warning(f"Short citation could not be verified: '{citation.snippet}'")

        return verified