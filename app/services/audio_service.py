"""AudioService — British female voice narration using Google TTS."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional, Tuple

from gtts import gTTS
from pydub import AudioSegment

from app.core.config import get_settings
from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


class AudioService:
    """Generate British voice narration using Google TTS (100% free, reliable)."""

    def __init__(self):
        self.output_dir = Path(settings.audio_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.storage = get_storage_service()

    async def generate_audio(
        self,
        text: str,
        lang: str = "en",
        tld: str = "co.uk",  # British English accent
    ) -> Tuple[str, int]:
        """
        Generate audio using Google TTS with British accent.

        Args:
            text: Text to convert to speech
            lang: Language code (default: English)
            tld: Top-level domain for accent (co.uk = British)

        Returns:
            Tuple of (public_url_or_path, duration_seconds)
        """
        filename = f"narration_{uuid.uuid4().hex[:12]}.mp3"
        local_file_path = self.output_dir / filename

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generating audio ({len(text)} chars) - attempt {attempt + 1}/{MAX_RETRIES}")

                # Generate audio in thread pool (gTTS is synchronous)
                await self._generate_gtts(text, str(local_file_path), lang, tld)

                # Get duration before potentially uploading
                duration = await self._get_duration(str(local_file_path))
                logger.info(f"Audio generated: {filename} ({duration:.1f}s)")

                # Upload to cloud storage (or keep local path)
                success, url_or_path = await self.storage.upload_file(
                    str(local_file_path),
                    f"audio/{filename}",
                    content_type="audio/mpeg"
                )

                if success:
                    return url_or_path, duration
                else:
                    # Fallback to local path if upload fails
                    logger.warning("Cloud upload failed, using local storage")
                    return str(local_file_path), duration

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"gTTS failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Audio generation failed after {MAX_RETRIES} attempts: {e}")

        raise last_error

    async def _generate_gtts(self, text: str, file_path: str, lang: str, tld: str) -> None:
        """Generate audio file using gTTS in a thread pool."""
        def sync_generate():
            tts = gTTS(text=text, lang=lang, tld=tld)
            tts.save(file_path)

        await asyncio.to_thread(sync_generate)

    async def _get_duration(self, file_path: str) -> int:
        """Get audio duration in whole seconds using pydub."""
        def load():
            try:
                audio = AudioSegment.from_mp3(file_path)
                return round(len(audio) / 1000.0)  # Round to nearest whole second
            except Exception:
                return 0

        return await asyncio.to_thread(load)

    async def delete_audio(self, file_path_or_url: str) -> bool:
        """Delete an audio file from storage (cloud or local)."""
        try:
            return await self.storage.delete_file(file_path_or_url)
        except Exception as e:
            logger.warning(f"Failed to delete audio file: {e}")
        return False

    def get_audio_url(self, file_path_or_url: str) -> Optional[str]:
        """Get the public URL for an audio file."""
        if not file_path_or_url:
            return None
        return self.storage.get_public_url(file_path_or_url)
