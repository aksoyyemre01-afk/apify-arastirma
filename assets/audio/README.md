# assets/audio/ — müzik ve ses efektleri (RULES.md kural 8)

Render bu klasördeki dosyaları **varsa** otomatik kullanır (isimler birebir eşleşmeli).
Dosya yoksa o katman sessizce atlanır; video yine normal üretilir.

| Dosya | Ne zaman çalar | Kaynak |
|---|---|---|
| `music.mp3` | Tüm video boyunca döngüde, sonda yumuşak kapanış | Sizin lisanslı müziğiniz (repoya girmez, `.gitignore`'da) |
| `whoosh.mp3` | Sahne geçişlerinde (en az 1,5 sn arayla; impact ile çakışanlar atlanır) | `tools/make_sfx.py` ile sentezlenir (repoda) |
| `impact.mp3` | Gizemli hook'ta markanın açığa çıktığı an ve düşüş grafiklerinin başında | `tools/make_sfx.py` ile sentezlenir (repoda) |

Efektleri yeniden üretmek için: `python tools/make_sfx.py`

## Seviyeler (müzik ve efektler asla seslendirmeyi bastırmaz)

Seviyeler sabit kazançla değil, seslendirmenin **ölçülen** seviyesine göre ayarlanır;
böylece çok yüksek masterlanmış bir müzik ya da efekt dosyası da konuşmanın altında kalır.
Ayarlar `config/brand.json` → `audio`:

- `music_below_voice_db` (15): müziğin taban seviyesi, seslendirmenin kaç dB altında.
  Ayrıca konuşma olan anlarda sidechain ducking müziği ek olarak kısar; duraklamalarda
  ve outro'da taban seviyeye döner. Müzik render'dan sonra `src/renderer.py` içinde eklenir.
- `whoosh_below_voice_db` (12) ve `impact_below_voice_db` (6): efektin, seslendirmenin kaç
  dB altında olacağı (`src/scene_planner.py` `_sfx_gain`).

Son olarak tüm mix -14 LUFS'a normalize edilir.

Müzik kaynağı önerileri: [Pixabay Music](https://pixabay.com/music/), YouTube Audio Library.
