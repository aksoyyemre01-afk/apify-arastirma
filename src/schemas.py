from pydantic import BaseModel, Field


class ShortScript(BaseModel):
    title: str = Field(description="Videonun çekici, tıklanabilir başlığı")
    hook: str = Field(description="İlk 3 saniyede izleyiciyi durduracak açılış cümlesi")
    narration: str = Field(description="Seslendirme metninin tamamı (hook dahil), tek parça, doğal konuşma dili")
    visual_notes: list[str] = Field(description="Sahne/görsel yönlendirme notları, kısa maddeler halinde")
    cta: str = Field(description="Videonun sonundaki çağrı (takip et, yorum yap vb.)")
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
