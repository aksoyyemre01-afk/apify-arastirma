"""İndirilen stok görsel/video karesinin arama sorgusuyla/sahne açıklamasıyla
gerçekten konuyla alakalı olup olmadığını Gemini vision ile kontrol eder.

Best-effort bir filtredir: GEMINI_API_KEY tanımlı değilse veya çağrı başarısız
olursa, filtre devre dışı kalır (her zaman "alakalı" kabul edilir) - pipeline
bu yüzden asla durmaz, sadece ekstra bir güvenlik katmanı eksik kalır."""

import os
import subprocess
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

_client = None
_client_tried = False


def _get_client():
    global _client, _client_tried
    if _client_tried:
        return _client
    _client_tried = True
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai

    _client = genai.Client(api_key=api_key)
    return _client


def _extract_frame(video_path: Path) -> Path | None:
    """Alaka kontrolü için videodan temsili bir kare çıkarır (1. saniye, yoksa ilk kare)."""
    frame_path = video_path.with_suffix(".check.jpg")
    for seek_args in (["-ss", "00:00:01"], []):
        result = subprocess.run(
            ["ffmpeg", "-y", *seek_args, "-i", str(video_path), "-frames:v", "1", str(frame_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and frame_path.exists():
            return frame_path
    return None


def is_relevant(media_path: Path, kind: str, query: str, note: str) -> bool:
    """Görsel/video sahnenin arama sorgusu ve sahne açıklamasıyla görsel olarak
    konuyla alakalı olup olmadığını Gemini vision ile kontrol eder."""
    client = _get_client()
    if client is None:
        return True

    image_path = media_path
    temp_frame: Path | None = None
    if kind == "video":
        temp_frame = _extract_frame(media_path)
        if temp_frame is None:
            return True  # kare çıkarılamadıysa filtreleme yapılamaz, engelleme
        image_path = temp_frame

    try:
        from google.genai import types

        image_bytes = image_path.read_bytes()
        prompt = (
            "Bu görsel, bir video sahnesi için stok medya olarak kullanılacak.\n"
            f'Sahne açıklaması: "{note}"\n'
            f'Arama sorgusu: "{query}"\n\n'
            "Bu görsel, sahne açıklamasıyla KONUYLA İLGİLİ mi (aynı sektör/ürün/tema/dönem)? "
            "Rastgele veya ilgisiz bir stok görselse (ör. sahne bir telefon şirketiyle "
            "ilgiliyken görsel bir tekstil fabrikasıysa, ya da sahne bir kriz anıyla "
            "ilgiliyken görsel iki kişinin gülümseyerek tokalaştığı alakasız bir kurumsal "
            "fotoğrafsa) HAYIR de. Sadece tek kelime cevap ver: EVET ya da HAYIR."
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt],
        )
        answer = (response.text or "").strip().upper()
        return answer.startswith("E")
    except Exception:
        return True
    finally:
        if temp_frame is not None:
            temp_frame.unlink(missing_ok=True)
