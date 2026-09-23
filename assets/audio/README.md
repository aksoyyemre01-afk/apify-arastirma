# assets/audio/ — ses tasarımı dosyaları

`src/audio_mix.py`, video birleştirme sırasında burada aşağıdaki dosyaları
**varsa** otomatik kullanır (isim birebir eşleşmeli). Dosya yoksa o katman
sessizce atlanır — hiçbir şey burada olmasa da video normal üretilir.

| Dosya | Ne için | Süre/format önerisi |
|---|---|---|
| `music.mp3` | Arka plan müziği, tüm video boyunca döngüye alınır, seslendirmenin -18/-22 dB altında miksajlanır | En az video kadar uzun (döngülenir), telifsiz/lisanslı gerilim müziği, mp3 |
| `whoosh.mp3` | Rakam kartları (üretilen stat/karşılaştırma grafikleri) ekrana geldiğinde çalınır | ~0.3-0.8 sn, kısa "whoosh" efekti |
| `impact.mp3` | twist (dramatik/çöküş anı) sahnesi başladığında çalınır | ~0.5-1.5 sn, "impact"/"hit" tarzı efekt |

## Nereden bulunur (telifsiz/ücretsiz kaynaklar)

- **Müzik:** [Pixabay Music](https://pixabay.com/music/) (telifsiz), [YouTube Audio Library](https://studio.youtube.com) (ücretsiz, "tension"/"dramatic" etiketli bir parça ara)
- **Whoosh/impact SFX:** [Pixabay Sound Effects](https://pixabay.com/sound-effects/) - "whoosh" ve "impact"/"hit" ile ara, 1-2 saniyelik kısa dosyalar seç

Dosyaları indirip bu klasöre `music.mp3`, `whoosh.mp3`, `impact.mp3` adlarıyla
koyman yeterli — kod tarafında başka bir ayar gerekmez.
