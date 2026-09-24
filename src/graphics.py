"""Pillow ile "üretilen grafik" sahneleri üretir (RULES.md kural 16).

Script'te geçen önemli bir rakam (şirket değeri, teklif tutarı, kullanıcı sayısı)
için büyük puntolu bir "istatistik kartı", iki taraf karşılaştırması için (ör.
Yahoo vs Google) yan yana bir "karşılaştırma kartı" üretir. Seri boyunca aynı
renk paletini kullanır (PALETTE) - tutarlı marka görünümü için.
"""

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1920

PALETTE = {
    "background": (17, 20, 40),       # koyu lacivert - PLACEHOLDER_COLORS ile uyumlu
    "background_alt": (10, 12, 24),
    "text": (255, 255, 255),
    "accent_negative": (255, 71, 87),  # kırmızı - düşüş/kriz rakamları için
    "accent_positive": (46, 213, 115), # yeşil - artış rakamları için
    "muted": (160, 165, 190),
}

_FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (Ubuntu/Debian, GitHub Actions)
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",  # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",  # Windows
    "C:/Windows/Fonts/segoeuib.ttf",
]
_FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # Hiçbir sistem fontu bulunamadıysa (nadir) Pillow'un dahili fontuna düş -
    # düşük kaliteli ama asla çökmez.
    return ImageFont.load_default(size=size)


# Rakam algılama: "120 milyar dolar", "$50 million", "4.8 milyar", "%90" gibi
# somut büyüklük belirten ifadeleri yakalar; bağlamsız 4 haneli yıl sayılarını
# (ör. "1975'te") dışarıda bırakmaya çalışır.
_MAGNITUDE_WORDS = r"(milyar|milyon|bin|%|dolar|\$|TL|₺|kullanıcı)"
_STAT_PATTERN = re.compile(
    rf"(\$?\s?\d[\d.,]*\s*{_MAGNITUDE_WORDS}|{_MAGNITUDE_WORDS}\s?\d[\d.,]*)",
    re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def extract_stat(text: str) -> str | None:
    """text içinde somut bir büyüklük/rakam ifadesi varsa (ör. '44.6 milyar dolar')
    onu döner, yoksa None. Kartın KISA etiketi burada üretilmez - notun geri kalanı
    bir cümle kadar uzun olabileceğinden (kural 22) bunun yerine
    keywords.clean_stat_label() ile 1-3 kelimelik bir etiket üretilmeli."""
    match = _STAT_PATTERN.search(text)
    if not match:
        return None
    number_text = match.group(0).strip()
    # Sadece bir yıl ifadesiyle eşleşmiş olabilir (ör. "1975" -> "%" yakalamaz ama
    # emin olmak için ayrıca kontrol) - yıl-only eşleşmeleri filtrele.
    if _YEAR_PATTERN.fullmatch(number_text.strip()):
        return None
    return number_text


_COMPARISON_PATTERN = re.compile(r"(.+?)\s+(?:vs\.?|karşı(?:sında)?|karşılık)\s+(.+)", re.IGNORECASE)


def extract_comparison(text: str) -> tuple[str, str] | None:
    """text içinde 'X vs Y' / 'X karşı Y' tarzı bir karşılaştırma varsa
    (left_label, right_label) döner, yoksa None."""
    match = _COMPARISON_PATTERN.search(text)
    if not match:
        return None
    left = match.group(1).strip(" ,.-")[:30]
    right = match.group(2).strip(" ,.-")[:30]
    if not left or not right:
        return None
    return left, right


def _draw_wrapped_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, y: int, fill, spacing: int = 12) -> int:
    """text'i max_width'e sığacak şekilde satırlara böler, ortalar, çizer.
    Bir sonraki serbest y koordinatını döner."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=fill)
        y += font.size + spacing
    return y


def render_stat_card(number_text: str, label_text: str, dest_dir: Path, index: int, dramatic: bool = False) -> Path:
    """Büyük puntolu bir rakam kartı üretir (ör. '120 Milyar $' + 'şirket değeri')."""
    bg = PALETTE["background_alt"] if dramatic else PALETTE["background"]
    accent = PALETTE["accent_negative"] if dramatic else PALETTE["accent_positive"]

    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    number_font = _load_font(140, bold=True)
    label_font = _load_font(48, bold=False)

    center_y = HEIGHT // 2
    number_h = number_font.size
    y = center_y - number_h - 40
    y = _draw_wrapped_text(draw, number_text, number_font, WIDTH - 160, y, accent, spacing=10)
    y += 30
    _draw_wrapped_text(draw, label_text, label_font, WIDTH - 240, y, PALETTE["text"])

    dest = dest_dir / f"gen_stat_{index:02d}.png"
    img.save(dest)
    return dest


def compose_logo_on_background(
    logo_path: Path, dest_dir: Path, index: int, background: tuple[int, int, int] = (255, 255, 255)
) -> Path:
    """Bir logo dosyasını (genelde Wikimedia'dan gelen şeffaf PNG/webp) düz renkli
    bir zemine (varsayılan beyaz) ortalayıp sığdırarak (contain, kırpma yok) tek
    parça bir görsel üretir. Bu adım önemli: şeffaf PNG'ler ffmpeg'in yuv420p
    kodlamasında şeffaflık desteklenmediği için siyah zemine dönüşür - PIL burada
    alfa kanalını doğru şekilde beyaz zemine karıştırır (RULES.md kural 22)."""
    canvas = Image.new("RGB", (WIDTH, HEIGHT), background)
    try:
        logo = Image.open(logo_path).convert("RGBA")
        # Logo, ekranın ~70%'ine (genişlik) / ~40%'ına (yükseklik) sığacak şekilde
        # küçültülür (contain) - hiçbir zaman kırpılmaz, tamamı her zaman görünür.
        logo.thumbnail((int(WIDTH * 0.7), int(HEIGHT * 0.4)))
        canvas.paste(
            logo,
            (int((WIDTH - logo.width) / 2), int((HEIGHT - logo.height) / 2)),
            logo,
        )
    except Exception:
        pass  # bozuk/okunamayan dosya - düz zemin döner, çağıran taraf yine de kullanabilir

    dest = dest_dir / f"gen_logo_{index:02d}.jpg"
    canvas.convert("RGB").save(dest, quality=92)
    return dest


def render_text_card(text: str, dest_dir: Path, index: int, dramatic: bool = False) -> Path:
    """Hiçbir uygun stok/marka görseli bulunamadığında (kural 24) son çare olarak
    kullanılan, sahnenin kendi metnini gösteren sade bir kart - alakasız bir stok
    fotoğraftan (ör. rastgele bir bina/alarm görseli) her zaman daha güvenlidir."""
    bg = PALETTE["background_alt"] if dramatic else PALETTE["background"]
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    font = _load_font(56, bold=True)
    y = HEIGHT // 2 - 100
    _draw_wrapped_text(draw, text[:120], font, WIDTH - 200, y, PALETTE["text"], spacing=16)

    dest = dest_dir / f"gen_text_{index:02d}.png"
    img.save(dest)
    return dest


def render_comparison_card(
    left_label: str, right_label: str, dest_dir: Path, index: int,
    left_logo: Path | None = None, right_logo: Path | None = None,
) -> Path:
    """İki taraf karşılaştırma kartı üretir (ör. 'Yahoo' vs 'Google'). left_logo/
    right_logo verilirse (ör. Wikimedia'dan indirilmiş gerçek logolar) metin yerine
    logo görseli kullanılır."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PALETTE["background"])
    draw = ImageDraw.Draw(img)

    name_font = _load_font(72, bold=True)
    vs_font = _load_font(90, bold=True)

    col_width = WIDTH // 2
    center_y = HEIGHT // 2
    logo_box = (col_width - 80, 320)

    def _place(label: str, logo: Path | None, x_center: int) -> None:
        if logo and logo.exists():
            try:
                logo_img = Image.open(logo).convert("RGBA")
                logo_img.thumbnail(logo_box)
                img.paste(
                    logo_img,
                    (int(x_center - logo_img.width / 2), int(center_y - logo_img.height / 2)),
                    logo_img,
                )
                return
            except Exception:
                pass
        w = draw.textlength(label, font=name_font)
        draw.text((x_center - w / 2, center_y - name_font.size / 2), label, font=name_font, fill=PALETTE["text"])

    _place(left_label, left_logo, col_width // 2)
    _place(right_label, right_logo, col_width + col_width // 2)

    vs_text = "VS"
    vw = draw.textlength(vs_text, font=vs_font)
    draw.ellipse(
        [WIDTH / 2 - 70, center_y - 70, WIDTH / 2 + 70, center_y + 70],
        fill=PALETTE["accent_negative"],
    )
    draw.text((WIDTH / 2 - vw / 2, center_y - vs_font.size / 2), vs_text, font=vs_font, fill=PALETTE["text"])

    dest = dest_dir / f"gen_compare_{index:02d}.png"
    img.save(dest)
    return dest
