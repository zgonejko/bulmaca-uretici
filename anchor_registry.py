"""Daha önce üretilmiş bulmacaların 'anchor' çiftini (en üstteki 6 harfli +
en soldaki 8 harfli kelime) kalıcı olarak saklar. Bu ikili bulmacanın geri
kalanını neredeyse tamamen belirlediği için, aynı ikilinin tekrar
kullanılmasını engellemek, iki farklı çalıştırmada aynı/çok benzer bir
bulmacanın üretilmesini büyük ölçüde önlüyor.

Excel'e yeni kelime/görsel eklemeniz bu dosyayı ETKİLEMEZ - kayıt, siz
elle silmediğiniz sürece kalıcı kalır, üretici dosyasını her çalıştırdığınızda
üstüne eklenir.
"""
import json
import os

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), 'uretilmis_bulmacalar.json')


def load_used_anchors(path=DEFAULT_PATH):
    if not os.path.exists(path):
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {tuple(pair) for pair in data.get('anchors', [])}


def save_used_anchor(row1_word, col1_word, path=DEFAULT_PATH):
    """Yeni üretilen bir bulmacanın anchor çiftini kayda EKLER (mevcut
    kayıtları silmez)."""
    existing = load_used_anchors(path)
    existing.add((row1_word, col1_word))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'anchors': [list(p) for p in sorted(existing)]}, f, ensure_ascii=False, indent=2)
