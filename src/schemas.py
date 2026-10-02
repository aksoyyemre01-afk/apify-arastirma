"""Gemini structured-output şemaları.

RULES.md kural 1/2/10: script ve her cümlenin sahnesi AYNI Gemini çağrısında
üretilir. Her `Scene` tek bir kısa cümleyi (narration) ve o cümlede anlatılanı
doğrudan gösteren kodla çizilmiş bir hareketli grafiği (scene_type + alanları)
tanımlar. Görsel arama yoktur. Ekranda görünen tüm metinler (value, unit,
label, text, cta...) kısa, izleyiciye yönelik metinlerdir; iç not/prompt
metni için bir alan yoktur.

Not: Gemini şeması union'ları iyi desteklemediği için sahne tipine özgü
alanlar düz ve opsiyoneldir; hangi tipin hangi alanı kullandığı alan
açıklamalarında yazar ve src/scene_planner.py bunu doğrular.
"""

from typing import Literal

from pydantic import BaseModel, Field

SceneType = Literal["logo_intro", "big_number", "comparison", "timeline", "chart", "quote"]


class Scene(BaseModel):
    narration: str = Field(
        description="Bu sahnede seslendirilecek TEK kısa cümle ya da yan cümle (5-10 kelime, "
        "~2-3 saniye). Tüm sahnelerin narration'ları art arda okununca videonun tam metni olur."
    )
    scene_type: SceneType = Field(
        description="Bu cümlede anlatılanı DOĞRUDAN gösteren sahne tipi: "
        "logo_intro=bir markayı tanıtan/açığa çıkaran logo kartı; "
        "big_number=cümledeki en önemli rakam (değer+birim+etiket); "
        "comparison=cümlede iki marka/taraf karşılaştırılıyor; "
        "timeline=cümlede bir yıl/tarih ve olay geçiyor; "
        "chart=cümlede yükseliş ya da düşüş anlatılıyor; "
        "quote=rakam/marka/yıl yoksa cümlenin vurucu özü."
    )
    brand: str = Field(
        default="",
        description="logo_intro'da gösterilecek marka. Diğer tiplerde cümlenin ilgili olduğu marka "
        "(küçük logo olarak gösterilir), yoksa boş.",
    )
    value: str = Field(
        default="",
        description="big_number: sadece sayı, Türkçe yazımla (ör. '125', '44,6', '1'). Başka tipte boş.",
    )
    unit: str = Field(
        default="",
        description="big_number: birim, BÜYÜK HARF (ör. 'MİLYAR $', 'MİLYON $', '%', 'KULLANICI').",
    )
    label: str = Field(
        default="",
        description="Kısa ekran etiketi, en fazla 5 kelime (ör. 'Piyasa değeri', 'Microsoft teklifi'). "
        "logo_intro'da markanın altındaki kısa ifade.",
    )
    left_brand: str = Field(default="", description="comparison: sol taraftaki marka/taraf.")
    right_brand: str = Field(default="", description="comparison: sağ taraftaki marka/taraf.")
    left_value: str = Field(default="", description="comparison: sol tarafın kısa değeri (ör. '1 MİLYON $'), yoksa boş.")
    right_value: str = Field(default="", description="comparison: sağ tarafın kısa değeri, yoksa boş.")
    highlight_side: Literal["none", "left", "right"] = Field(
        default="none", description="comparison: cümlenin vurguladığı taraf (kazanan/kaybeden), yoksa none."
    )
    year: str = Field(default="", description="timeline: yıl ya da dönem (ör. '1998', '2000'LER').")
    direction: Literal["none", "up", "down"] = Field(
        default="none", description="chart: up yükseliş, down düşüş; diğer tiplerde none."
    )
    points: list[float] = Field(
        default_factory=list,
        description="chart: 3-6 gerçekçi veri noktası (kronolojik). Bilinmiyorsa yönü yansıtan temsili değerler.",
    )
    point_labels: list[str] = Field(
        default_factory=list,
        description="chart: points ile aynı uzunlukta kısa etiketler (ör. yıllar) ya da boş liste.",
    )
    end_value: str = Field(
        default="", description="chart: son noktanın ekranda yazacak değeri (ör. '4,8 MİLYAR $'), yoksa boş."
    )
    text: str = Field(
        default="",
        description="quote: ekranda gösterilecek vurucu cümle, en fazla 8 kelime. timeline: olayın kısa "
        "açıklaması (en fazla 6 kelime).",
    )
    highlight: list[str] = Field(
        default_factory=list, description="quote: text içinden vurgulanacak 1-2 kelime (birebir aynı yazımla)."
    )
    mood: Literal["neutral", "rise", "fall"] = Field(
        default="neutral",
        description="Cümlenin yönü: rise=zirve/büyüme/başarı, fall=düşüş/kayıp/kriz/kötü karar, "
        "neutral=ikisi de değil. Zemin tonunu belirler.",
    )
    reveal: bool = Field(
        default=False,
        description="Gizemli hook'ta cevap olan markanın açığa çıktığı sahne ise true (sadece bir sahnede).",
    )


class ShortScript(BaseModel):
    title: str = Field(description="Videonun çekici, tıklanabilir başlığı")
    main_brand: str = Field(description="Videonun ana konusu olan marka/şirket")
    hook_type: Literal["mystery", "direct"] = Field(
        description="mystery: hook bir soru/gizem kuruyor ve cevap olan marka ilk cümlede söylenmiyor "
        "(ilk sahne bağlamı gösterir, marka soru işaretli kutuyla gizlenir). direct: ana marka ilk "
        "sahnede doğrudan görünür."
    )
    mystery_brand: str = Field(
        default="",
        description="hook_type=mystery ise gizlenen/cevap olan marka (genellikle main_brand), yoksa boş.",
    )
    reveal_by_seconds: float = Field(
        default=0.0,
        description="hook_type=mystery ise markanın sesli söylenip açığa çıkacağı en geç saniye (<= 5). "
        "direct ise 0.",
    )
    scenes: list[Scene] = Field(
        description="Videonun tüm cümleleri, sırayla; her biri kendi sahnesiyle (toplam 12-18 sahne)."
    )
    cta: str = Field(
        description="Kapanışta ekranda görünecek, merak uyandıran kısa metin (en fazla 10 kelime, seslendirilmez)."
    )
    hashtags: list[str] = Field(description="YouTube Shorts için önerilen hashtag listesi")

    @property
    def narration_full(self) -> str:
        return " ".join(s.narration.strip() for s in self.scenes)


class SceneLayout(BaseModel):
    """Seslendirmesi zaten var olan eski script'ler için: sabit metni değiştirmeden
    yalnızca sahne yapısını üretir (build_video.py --migrate)."""

    main_brand: str
    hook_type: Literal["mystery", "direct"]
    mystery_brand: str = ""
    reveal_by_seconds: float = 0.0
    scenes: list[Scene]
    cta: str


class LongChapter(BaseModel):
    heading: str = Field(description="Bölüm başlığı")
    narration: str = Field(description="Bu bölümün seslendirme metni")
    scenes: list[Scene] = Field(
        default_factory=list,
        description="Bu bölümün cümleleri ve her cümlenin sahnesi (narration'ların birleşimi bölüm metnidir).",
    )


class LongScript(BaseModel):
    title: str = Field(description="Videonun başlığı")
    main_brand: str = Field(default="", description="Videonun ana konusu olan marka/şirket")
    hook: str = Field(description="İlk 15 saniyelik açılış / merak uyandırma metni")
    chapters: list[LongChapter] = Field(description="Videonun bölümleri (giriş, yükseliş, hata/kriz, sonuç, ders)")
    cta: str = Field(description="Videonun sonundaki çağrı")
    hashtags: list[str] = Field(description="YouTube için önerilen hashtag/etiket listesi")

    @property
    def full_narration(self) -> str:
        return "\n\n".join(f"{c.heading}\n{c.narration}" for c in self.chapters)


# ---------------------------------------------------------------------------- uzun video (16:9)
LongSceneType = Literal["logo_intro", "big_number", "comparison", "timeline", "chart", "quote", "photo"]


class LongScene(Scene):
    scene_type: LongSceneType = Field(
        description="Short sahne tiplerine ek olarak 'photo': cümlede adı geçen gerçek bir kişinin/kurumun/"
                    "yerin arşiv fotoğrafı; konu adı `brand` alanına yazılır (fotoğraf o ad söylenirken görünür).")


class LongSection(BaseModel):
    heading: str = Field(default="", description="Bölüm başlığı (seslendirmede okunur ve bölüm kartında görünür); "
                                                  "hook ve kapanışta boş.")
    narration: str = Field(description="Bu bölümün seslendirme metni (başlık hariç)")
    scenes: list[LongScene] = Field(description="Bu bölümün cümleleri ve her cümlenin sahnesi; narration'ların "
                                                "birleşimi bölüm metnidir.")


class LongVideoScript(BaseModel):
    title: str = Field(description="YouTube başlığı (en fazla 90 karakter)")
    main_brand: str = Field(description="Videonun ana konusu olan marka/şirket")
    hook: LongSection = Field(description="20-30 saniyelik açılış (heading boş)")
    chapters: list[LongSection] = Field(description="3-4 bölüm, kronolojik; her biri başlıklı")
    closing: LongSection = Field(description="Kapanış: ders ve izleyiciye soru (heading boş)")
    cta: str = Field(description="Kapanış kartındaki kısa çağrı (en fazla 8 kelime)")
    description: str = Field(description="YouTube açıklamasının giriş paragrafı (bölümler ve atıflar otomatik eklenir)")
    tags: list[str] = Field(description="10-15 YouTube etiketi")
    thumbnail_value: str = Field(default="", description="Küçük resimdeki büyük rakam (doğrulanmış olgulardan), yoksa boş")
    thumbnail_unit: str = Field(default="", description="Rakamın birimi (ör. 'MİLYAR $'), yoksa boş")
    thumbnail_headline: str = Field(default="", description="Küçük resimde en fazla 5 kelimelik çarpıcı başlık")

    def sections(self) -> list[tuple[str, LongSection]]:
        return [("hook", self.hook)] + [(f"bolum-{i}", c) for i, c in enumerate(self.chapters, 1)] + [("kapanis", self.closing)]

    @property
    def narration_full(self) -> str:
        return " ".join(section_text(s) for _, s in self.sections())


def section_text(s: "LongSection") -> str:
    """Bölümün seslendirilen metni: başlık (varsa) + metin."""
    head = s.heading.strip()
    if head and not head.endswith((".", "!", "?", ":")):
        head += "."
    return f"{head} {s.narration}".strip() if head else s.narration.strip()
