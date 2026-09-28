"""Sessiz alt süreç çağrıları.

Windows'ta konsolu olmayan bir süreçten (arka plan işçisi, pythonw, Görev Zamanlayıcı)
başlatılan her konsol programı (ffmpeg, ffprobe, node, powershell, tasklist) kendine yeni,
görünür bir pencere açar. Buradaki run() her çağrıya CREATE_NO_WINDOW ekler; projedeki tüm
alt süreç çağrıları bunu kullanır. Diğer işletim sistemlerinde subprocess.run ile aynıdır.
"""

import os
import subprocess

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run(*args, **kwargs) -> subprocess.CompletedProcess:
    if NO_WINDOW:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | NO_WINDOW
    return subprocess.run(*args, **kwargs)
