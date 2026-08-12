from __future__ import annotations

from openai import AsyncOpenAI

from app.config import config

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.groq_api_key, base_url="https://api.groq.com/openai/v1")
    return _client


async def transcribe_voice(audio_bytes: bytes) -> str:
    client = _get_client()
    response = await client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=("voice.ogg", audio_bytes),
        language="ru",
    )
    return response.text.strip()
