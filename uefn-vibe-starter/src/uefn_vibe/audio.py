"""PCM brut (s16le mono) -> WAV, le format que UEFN importe sans surprise."""
from __future__ import annotations

import io
import wave


def pcm16_to_wav(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    if len(pcm) % (2 * channels):
        pcm = pcm[: len(pcm) - (len(pcm) % (2 * channels))]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()
