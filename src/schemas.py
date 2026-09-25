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
