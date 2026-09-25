# assets/audio/ — müzik ve ses efektleri (RULES.md kural 8)

Video render'ı (`src/scene_planner.py` → Remotion) burada aşağıdaki dosyaları
**varsa** otomatik kullanır (isim birebir eşleşmeli). Dosya yoksa o katman
sessizce atlanır — video yine normal üretilir.

| Dosya | Ne zaman çalar | Öneri |
|---|---|---|
| `music.mp3` | Tüm video boyunca döngüde, `config/brand.json` → `audio.music_volume_db` seviyesinde (varsayılan -20 dB), sonda yumuşak kapanış | Telifsiz, gerilimli/ritmik bir parça |
| `whoosh.mp3` | Sahne geçişlerinde (en az 1,5 sn arayla) | ~0.3-0.8 sn kısa whoosh |
| `impact.mp3` | Gizemli hook'ta markanın açığa çıktığı an ve düşüş grafiklerinin başında | ~0.5-1.5 sn impact/hit |

Kaynak önerileri: [Pixabay Music](https://pixabay.com/music/), [Pixabay Sound Effects](https://pixabay.com/sound-effects/),
YouTube Audio Library. `*.mp3` dosyaları .gitignore'dadır (repoya girmez).
