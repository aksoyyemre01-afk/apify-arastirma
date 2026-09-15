"""ElevenLabs ile seslendirme üretimi."""

import os

from elevenlabs.client import ElevenLabs

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel" varsayılan sesi

_client: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY tanımlı değil (.env dosyasını kontrol et)")
        _client = ElevenLabs(api_key=api_key)
    return _client


def synthesize(text: str, output_path: str) -> None:
    client = _get_client()
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
    model_id = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=text,
    )

    with open(output_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)
