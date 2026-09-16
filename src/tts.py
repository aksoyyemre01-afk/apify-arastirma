"""ElevenLabs ile seslendirme üretimi."""

import base64
import os

from elevenlabs.client import ElevenLabs

# "Brian" - ElevenLabs hesaplarına otomatik eklenen premade seslerden biri,
# free planda API üzerinden kullanılabilir (library/shared sesler free planda kullanılamaz).
DEFAULT_VOICE_ID = "nPczCjzI2devNBz1zQrb"

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


def _characters_to_words(characters: list[str], starts: list[float], ends: list[float]) -> list[dict]:
    """Karakter bazlı zaman kodlarını (ElevenLabs 'with-timestamps' çıktısı) kelime
    bazlı [{'word':.., 'start':.., 'end':..}, ...] listesine indirger."""
    words: list[dict] = []
    current_chars: list[str] = []
    current_start: float | None = None
    prev_end = 0.0

    for ch, start, end in zip(characters, starts, ends):
        if ch.isspace():
            if current_chars:
                words.append({"word": "".join(current_chars), "start": current_start, "end": prev_end})
                current_chars = []
                current_start = None
            continue
        if current_start is None:
            current_start = start
        current_chars.append(ch)
        prev_end = end

    if current_chars:
        words.append({"word": "".join(current_chars), "start": current_start, "end": prev_end})

    return words


def synthesize_with_timestamps(text: str, output_path: str) -> list[dict] | None:
    """Ses dosyasını üretir; mümkünse ElevenLabs'in karakter bazlı zaman kodlarından
    kelime bazlı zamanlama listesi de döner. Timestamp endpoint'i kullanılamazsa
    (SDK/plan/hesap desteklemiyorsa) sessizce düz `synthesize()`'a düşer ve None döner
    - çağıran taraf bu durumda altyazı için tahmini zamanlamaya geçmeli."""
    try:
        client = _get_client()
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
        model_id = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

        result = client.text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            model_id=model_id,
            text=text,
        )

        audio_bytes = base64.b64decode(result.audio_base64)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        alignment = result.alignment
        return _characters_to_words(
            alignment.characters,
            alignment.character_start_times_seconds,
            alignment.character_end_times_seconds,
        )
    except Exception:
        synthesize(text, output_path)
        return None
