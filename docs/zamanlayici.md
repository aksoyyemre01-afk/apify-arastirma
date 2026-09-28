# Haftalık otomatik tetikleme — Windows Görev Zamanlayıcı

Görev her hafta (öneri: pazartesi 08:00) `pipeline.py --week` komutunu **konsolsuz**
`pythonw.exe` ile çalıştırır: haftanın konusu seçilir, 3 bölüme ayrılır ve
`runs\<yıl>-W<hafta>\review.md` hazırlanır; ardından bir Windows bildirimi gelir. Hiçbir
pencere açılmaz: çıktı `runs\pipeline-konsol.log` dosyasına yazılır, arka plan üretimi ve
tüm ffmpeg/Node çağrıları gizli çalışır.
**Üretim sizin onayınızla başlar**; zamanlayıcı yalnızca ilk adımı yapar.

```
pazartesi 08:00  zamanlayıcı -> pipeline.py --week -> review.md + bildirim ("Haftanın konusu hazır")
siz              python pipeline.py --approve        -> 3 short arka planda üretilir (~15-25 dk)
                                                     -> review.md + bildirim ("Haftanın videoları hazır")
siz              python pipeline.py --approve        -> videolar yayina-hazir\<hafta>\ klasörüne
```

## Ön koşullar (bir kez)

1. `.env` dosyasında `GEMINI_API_KEY` ve `ELEVENLABS_API_KEY` dolu olmalı.
2. Elle bir kez deneyin (PowerShell):
   ```powershell
   cd "<proje klasörü>"
   & ".\.venv\Scripts\python.exe" "pipeline.py" --week
   ```
   `runs\...\review.md` oluşuyor ve bildirim geliyorsa hazırsınız. Denemeyi istemiyorsanız
   `runs\` altındaki o haftanın klasörünü silebilirsiniz.

## Kurulum — yöntem 1: PowerShell (önerilen, tek komut)

PowerShell'i **normal kullanıcı olarak** açın (yönetici gerekmez), **proje klasörüne geçin**
(`cd "<proje klasörü>"`) ve çalıştırın. Klasör yolu bulunduğunuz yerden alınır; hiçbir yolu
elle yazmanız gerekmez:

```powershell
$repo = (Get-Location).Path
$action  = New-ScheduledTaskAction -Execute "`"$repo\.venv\Scripts\pythonw.exe`"" `
            -Argument "`"$repo\pipeline.py`" --week" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "ShortPipeline-Haftalik" -Action $action -Trigger $trigger -Settings $settings `
            -Description "Haftalık short konusu ve plan (pipeline.py --week)" -Force
```

- Proje yolu boşluk içerebilir (ör. `YouTube Projesi`); bu yüzden program ve betik yolu
  tırnak içinde verilir (`` `" `` PowerShell'de çift tırnağın kaçışıdır). **Çalışma klasörü
  (`-WorkingDirectory`) ise tırnaksız kalmalıdır**: Görev Zamanlayıcı bu alanda tırnak kabul
  etmez, tırnaklıyken görev 0x8007010B ("dizin adı geçersiz") hatasıyla başlamaz.
- `-StartWhenAvailable`: bilgisayar pazartesi 08:00'de kapalıysa, açıldığında görev
  hemen çalışır.
- Görev yalnızca siz oturum açmışken çalışır. Bu bilerek böyle: bildirimin görünmesi
  ve `.env`/`PATH` ayarlarınızın (ffmpeg, Node) geçerli olması için gerekli.

## Kurulum — yöntem 2: Görev Zamanlayıcı arayüzü

1. Başlat menüsünde **Görev Zamanlayıcı**'yı açın → sağda **Görev Oluştur...** (Temel Görev değil).
2. **Genel** sekmesi:
   - Ad: `ShortPipeline-Haftalik`
   - "Yalnızca kullanıcı oturum açtığında çalıştır" seçili kalsın.
   - "En yüksek ayrıcalıklarla çalıştır" işaretlemeyin.
3. **Tetikleyiciler** → **Yeni...** → "Zamanlamaya göre", **Haftalık**, başlangıç saati
   `08:00`, **Pazartesi** işaretli → Tamam.
4. **Eylemler** → **Yeni...** → "Program başlat":
   - Program/komut dosyası: `"<proje klasörü>\.venv\Scripts\pythonw.exe"` (tırnaklarla)
   - Bağımsız değişkenler: `"<proje klasörü>\pipeline.py" --week` (tırnaklarla)
   - Başlama yeri: `<proje klasörü>` (**tırnaksız**; bu alan tırnak kabul etmez, boşluk sorun değildir)
   (`<proje klasörü>` yerine projenin tam yolunu yazın, ör. `C:\Users\<kullanıcı>\YouTube Projesi`;
   Görev Zamanlayıcı göreli yol kabul etmez.)
   (`pythonw.exe` konsolsuzdur; `python.exe` yazarsanız her pazartesi bir pencere açılır.)
5. **Koşullar**: "Bilgisayar AC güçteyse başlat" işaretini kaldırın (dizüstünde pilde de çalışsın).
6. **Ayarlar**:
   - "Zamanlanmış başlatma kaçırılırsa görevi en kısa sürede çalıştır" işaretleyin.
   - "Görev şundan uzun sürerse durdur: 1 saat".
7. **Tamam**.

## Kurulum — yöntem 3: schtasks (tek satır)

Komut İstemi'nde (cmd) **proje klasörüne geçip** çalıştırın; `%CD%` bulunduğunuz klasörün yoludur
(yol boşluk içerebileceği için `\"...\"` ile tırnaklanır):

```bat
cd /d "<proje klasörü>"
schtasks /Create /TN "ShortPipeline-Haftalik" /TR "\"%CD%\.venv\Scripts\pythonw.exe\" \"%CD%\pipeline.py\" --week" /SC WEEKLY /D MON /ST 08:00 /F
```

Bu yöntemde "kaçırılırsa çalıştır" seçeneği ve çalışma klasörü ayarı yoktur (pipeline kendi
klasörünü bulur); "kaçırılırsa çalıştır" için arayüzden 6. adımı yapın.

## Proje klasörü taşınırsa ya da adı değişirse

Kod ve dokümanlar hiçbir sabit klasör yolu içermez; tüm yollar projenin kendi konumundan
hesaplanır. Ancak **zamanlanmış görev, oluşturulduğu andaki tam yolu saklar**. Klasörün adını
değiştirdikten sonra görevi yeni klasörde yeniden oluşturun (yukarıdaki yöntemlerden birini
yeni klasörde tekrar çalıştırmanız yeterli; `-Force`/`/F` ile eskisinin üzerine yazılır).

`.venv` de oluşturulduğu klasörün yolunu içerir; klasör taşınınca bozulabilir. Bozulursa
yeniden oluşturun:

```powershell
cd "<proje klasörü>"
Remove-Item -Recurse -Force ".venv"
python -m venv ".venv"
& ".\.venv\Scripts\python.exe" -m pip install -r "requirements.txt"
```

`python` komutu Microsoft Store'u açıyorsa (PATH'te yalnızca Store kısayolu var), Python'un tam
yolunu tırnak içinde kullanın, ör. `& "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe" -m venv ".venv"`.

## Test ve kontrol

```powershell
Start-ScheduledTask -TaskName "ShortPipeline-Haftalik"      # şimdi çalıştır
Get-ScheduledTaskInfo -TaskName "ShortPipeline-Haftalik"      # son çalışma zamanı ve sonucu (0 = başarılı)
Get-Content "runs\pipeline-konsol.log" -Tail 30               # görevin çıktısı (pythonw)
& ".\.venv\Scripts\python.exe" "pipeline.py" --status         # haftanın durumu ve maliyeti
```

Aynı hafta için ikinci bir çalıştırma başlatılmaz; görev yanlışlıkla iki kez çalışırsa ikincisi
"zaten var" diyerek çıkar.

## Kaldırma / durdurma

```powershell
Disable-ScheduledTask    -TaskName "ShortPipeline-Haftalik"   # geçici olarak durdur
Unregister-ScheduledTask -TaskName "ShortPipeline-Haftalik" -Confirm:$false   # tamamen kaldır
```

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| Görev "0x1" ile bitti | `runs\pipeline-konsol.log`'a bakın. Çoğunlukla `.env` anahtarı eksiktir. |
| Bildirim gelmedi | Görev siz oturum açmamışken çalışmış olabilir; `review.md` yine oluşur. `--status` ile kontrol edin. |
| Üretim yarıda kaldı (bilgisayar kapandı) | `python pipeline.py --status` "DURMUŞ" der; `python pipeline.py --approve` kaldığı yerden devam ettirir. |
| "bütçe sınırı" bildirimi | Tahmini haftalık maliyet `config\pipeline.json` → `budget_usd_per_week` değerini aştı. `--approve` bir hafta sınırı kadar ek bütçe verip devam ettirir. |
