from pydantic import BaseModel, Field


class ShortBeat(BaseModel):
    narration: str = Field(description="Bu bölümün seslendirme metni, doğal konuşma dili")
    visual_notes: list[str] = Field(description="Bu bölüm için sahne/görsel yönlendirme notları")


class ShortScript(BaseModel):
    title: str = Field(description="Videonun çekici, tıklanabilir başlığı")
    hook: ShortBeat = Field(
        description="0-3 saniyelik açılış: izleyiciyi durduracak şok edici bir gerçek/soru/çelişki, "
        "~10-18 kelime, TEK güçlü açılış sahnesi"
    )
    setup: ShortBeat = Field(
        description="Kuruluş/bağlam bölümü: şirketin zirvesi/gücü neden böyleydi, ~35-50 kelime, 2 sahne"
    )
    twist: ShortBeat = Field(
        description="Senaryonun EN DRAMATİK anı: kritik hata/çöküş/kriz, ~30-45 kelime, 2 sahne; "
        "bu bölümün visual_notes'u MUTLAKA dramatik/yüksek kontrastlı, kriz hissi veren görseller "
        "tarif etmeli (kırmızı ışık, alarm, düşen grafik, enkaz, kapanan kapılar vb.)"
    )
    cta: str = Field(
        description="Videonun sonunda ekranda görünecek çağrı metni (takip et/yorum yap vb.); "
        "seslendirilmez, sadece görsel/alt yazı olarak kullanılır"
    )
    hashtags: list[str] = Field(description="YouTube Shorts için önerilen hashtag listesi")


class LongChapter(BaseModel):
    heading: str = Field(description="Bölüm başlığı")
    narration: str = Field(description="Bu bölümün seslendirme metni")


class LongScript(BaseModel):
    title: str = Field(description="Videonun başlığı")
    hook: str = Field(description="İlk 15 saniyelik açılış / merak uyandırma metni")
    chapters: list[LongChapter] = Field(description="Videonun bölümleri (giriş, yükseliş, hata/kriz, sonuç, ders)")
    cta: str = Field(description="Videonun sonundaki çağrı")
    hashtags: list[str] = Field(description="YouTube için önerilen hashtag/etiket listesi")

    @property
    def full_narration(self) -> str:
        return "\n\n".join(f"{c.heading}\n{c.narration}" for c in self.chapters)
