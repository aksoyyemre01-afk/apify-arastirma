"""Haftalık short üretimi için multi-agent pipeline (bkz. pipeline.py).

Araştırmacı -> Senarist -> Doğrulayıcı -> Yönetmen -> Eleştirmen. Agent'lar mevcut
src/ modüllerini (script_writer, tts, renderer, scene_planner) sarar; kuralların hepsi
geneldir, hiçbir konuya veya kanala özgü değildir.
"""
