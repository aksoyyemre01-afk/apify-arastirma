"""assets/audio/whoosh.mp3 ve impact.mp3 efektlerini ffmpeg ile sentezler.

Telifsiz, dışarıdan dosya gerektirmeyen, kısa ve temiz efektler (RULES.md kural 8):
- whoosh.mp3 (~0,7 sn): iki bantta süzülmüş pembe gürültü; ses önce koyu (düşük bant)
  sonra parlak (yüksek bant) duyulur ve soldan sağa geçer - sahne geçişi hissi.
- impact.mp3 (~1,3 sn): 110 Hz'den 42 Hz'e hızla inen alçak "boom", kısa bir vuruş
  geçişi (transient) ve hafif oda yankısı - reveal/düşüş anı için.
İkisi de 48 kHz stereo, tepe -1 dBFS'ye normalize edilir; videodaki seviye
config/brand.json -> audio.sfx_volume_db ile ayarlanır.

Kullanım:  python tools/make_sfx.py            (var olan dosyaların üzerine yazar)
"""

import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"
RATE = 48000


def _run(filter_complex: str, duration: float, dest: Path) -> None:
    # Önce ara WAV (tepe ölçümü için), sonra -1 dBFS tepeye normalize edilmiş MP3.
    wav = dest.with_suffix(".tmp.wav")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-filter_complex", filter_complex, "-map", "[out]",
         "-t", f"{duration}", "-ar", str(RATE), "-ac", "2", str(wav)],
        check=True,
    )
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    peak = float(probe.stderr.split("max_volume:")[1].split("dB")[0])
    gain = -1.0 - peak
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", f"volume={gain:.2f}dB",
         "-c:a", "libmp3lame", "-b:a", "192k", str(dest)],
        check=True,
    )
    wav.unlink()
    print(f"{dest.name}: {duration:.2f} sn, tepe -1 dBFS (kazanç {gain:+.1f} dB)")


def make_whoosh(dest: Path) -> None:
    d = 0.7
    # Zarf: 0,28 sn'de tepe yapan yumuşak şişme-sönme. Koyu bant erken, parlak bant geç.
    fc = (
        f"anoisesrc=d={d}:c=pink:r={RATE}:a=0.8:seed=7,asplit=2[n1][n2];"
        f"[n1]bandpass=f=700:width_type=o:w=1.2,"
        f"volume='exp(-pow((t-0.22)/0.12,2))':eval=frame[low];"
        f"[n2]bandpass=f=3200:width_type=o:w=1.4,"
        f"volume='0.8*exp(-pow((t-0.36)/0.13,2))':eval=frame[high];"
        f"[low][high]amix=inputs=2:normalize=0,"
        # soldan sağa geçiş (sabit güç)
        f"aformat=channel_layouts=stereo,"
        f"aeval='val(0)*cos(PI/2*min(t/{d},1))|val(1)*sin(PI/2*min(t/{d},1))':c=stereo,"
        f"afade=t=in:d=0.03,afade=t=out:st={d - 0.12}:d=0.12,"
        f"highpass=f=120,lowpass=f=9000[out]"
    )
    _run(fc, d, dest)


def make_impact(dest: Path) -> None:
    d = 1.3
    fc = (
        # Alçak boom: 42 Hz'e inen frekans (faz = integral), üstel sönüm.
        f"aevalsrc='sin(2*PI*(42*t+68*(1-exp(-14*t))/14))*exp(-3.2*t)':s={RATE}:d={d}[boom];"
        # Kısa vuruş: 40 ms'lik süzülmüş gürültü patlaması.
        f"anoisesrc=d={d}:c=white:r={RATE}:a=0.9:seed=11,lowpass=f=2500,"
        f"volume='exp(-70*t)':eval=frame[hit];"
        f"[boom][hit]amix=inputs=2:weights='1 0.45':normalize=0,"
        f"aformat=channel_layouts=stereo,"
        # Tek, yumuşak oda yansıması (birden fazla kısa tekrar çınlama/tırtık yapıyordu).
        f"aecho=0.85:0.5:140:0.12,"
        f"afade=t=out:st={d - 0.35}:d=0.35,highpass=f=28[out]"
    )
    _run(fc, d, dest)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_whoosh(OUT / "whoosh.mp3")
    make_impact(OUT / "impact.mp3")
