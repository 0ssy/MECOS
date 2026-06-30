"""
MECOS Meeting Assistant - Phase 1
Real-time meeting transcription with WASAPI loopback audio capture.
Uses agent_reach.transcribe for Whisper transcription with Groq/OpenAI fallback.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from loguru import logger

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("pyaudio not installed — audio capture disabled")

from agent_reach.transcribe import transcribe, TranscribeError
from config import settings


ASSISTANT_ENABLED = os.getenv("MECOS_ENABLE_ASSISTANT", "false").strip().lower() == "true"
CHUNK_SECONDS = 3
SAMPLE_RATE = 16000
FRAMES_PER_BUFFER = 1024


class MeetingAssistant:
    def __init__(self, memory_system=None):
        self.memory = memory_system
        self.audio = None
        self.stream = None
        self.running = False
        self.transcript_segments: list[str] = []
        self._loopback_available = False
        self._chunk_callback = None

    async def initialize(self) -> bool:
        if not PYAUDIO_AVAILABLE:
            return False
        try:
            self.audio = pyaudio.PyAudio()
            self._loopback_available = self._check_wasapi_loopback()
            if self._loopback_available:
                logger.info("WASAPI loopback available for system audio capture")
            else:
                logger.info("WASAPI loopback unavailable — microphone fallback will be used")
            return True
        except Exception as e:
            logger.error(f"MeetingAssistant initialization failed: {e}")
            return False

    def _check_wasapi_loopback(self) -> bool:
        if os.name != "nt":
            return False
        try:
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    name = info.get("name", "").lower()
                    if "wasapi" in name and "loopback" in name:
                        return True
        except Exception:
            pass
        return False

    def _open_loopback_stream(self):
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if "wasapi" in info.get("name", "").lower() and "loopback" in info.get("name", "").lower():
                return self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    input_device_index=i,
                    frames_per_buffer=FRAMES_PER_BUFFER,
                )
        return None

    def _open_microphone_stream(self):
        return self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )

    def _record_chunk(self, duration_seconds: float = CHUNK_SECONDS) -> bytes:
        if self.stream is None:
            return b""

        frames = []
        chunks_needed = int(SAMPLE_RATE / FRAMES_PER_BUFFER * duration_seconds)
        for _ in range(chunks_needed):
            try:
                data = self.stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                break
        return b"".join(frames)

    def _save_chunk(self, audio_data: bytes) -> Path:
        work_dir = Path(tempfile.mkdtemp(prefix="meeting_chunk-"))
        chunk_path = work_dir / "chunk.wav"
        try:
            import wave
            with wave.open(str(chunk_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data)
        except Exception as e:
            logger.debug(f"Failed to save audio chunk: {e}")
        return chunk_path

    async def _transcribe_chunk(self, chunk_path: Path) -> Optional[str]:
        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: transcribe(str(chunk_path), provider="auto", out_dir=chunk_path.parent),
            )
            return text.strip() if text else None
        except TranscribeError as e:
            logger.debug(f"Transcription failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Transcription error: {e}")
            return None
        finally:
            try:
                for f in chunk_path.parent.glob("*"):
                    f.unlink()
                chunk_path.parent.rmdir()
            except Exception:
                pass

    async def start_capture(self) -> AsyncGenerator[str, None]:
        if self.audio is None:
            yield ""
            return

        if self._loopback_available:
            self.stream = self._open_loopback_stream()
        else:
            self.stream = self._open_microphone_stream()

        if self.stream is None:
            yield ""
            return

        self.running = True
        logger.info("Meeting audio capture started")

        while self.running:
            audio_data = await asyncio.to_thread(self._record_chunk)
            if not audio_data:
                continue

            chunk_path = await asyncio.to_thread(self._save_chunk, audio_data)
            text = await self._transcribe_chunk(chunk_path)

            if text:
                self.transcript_segments.append(text)
                yield text

    async def stop_capture(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.audio:
            try:
                self.audio.terminate()
            except Exception:
                pass
        logger.info("Meeting audio capture stopped")

    def get_full_transcript(self) -> str:
        return "\n".join(self.transcript_segments)

    async def save_transcript(self) -> dict:
        if not self.transcript_segments:
            return {"status": "empty", "saved": False}

        full = self.get_full_transcript()
        if self.memory:
            try:
                await self.memory.add_experience(
                    content=f"MEETING TRANSCRIPT [{datetime.utcnow().isoformat()}]:\n{full[:10000]}",
                    source="meeting",
                )
            except Exception as e:
                logger.error(f"Failed to save transcript to memory: {e}")

        return {
            "status": "saved",
            "segments": len(self.transcript_segments),
            "chars": len(full),
        }