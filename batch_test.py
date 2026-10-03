"""Toplu üretim testi: asıl akışı (generate_puzzle: şablon + doldurma + anchor
kaydı + görsel/bayrak tercihi) N kez çalıştırır ve kuralları kontrol eder.

Kelime bankasının KENDİSİNE DOKUNMAMAK için Excel geçici bir kopyaya alınır;
anchor kaydı o kopyaya yazılır, test bitince silinir.

Kullanım:  python batch_test.py [bulmaca_sayısı] [excel_dosyası]
"""
import os
import random
import shutil
import sys
import tempfile
import time
from collections import Counter

from word_bank import WordBank, DEFAULT_XLSX
from slot_filler import _prefix_conflict
from puzzle_pipeline import generate_puzzle, SessionMemory
from export_json import puzzle_to_json
from anchor_registry import load_registry
from word_bank import TEK_HARFLI_CEVAP

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30

tmp_dir = tempfile.mkdtemp()
tmp_xlsx = os.path.join(tmp_dir, 'bulmaca_test_kopya.xlsx')
shutil.copy(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_XLSX, tmp_xlsx)
wb = WordBank(tmp_xlsx)

session_images = SessionMemory()   # aynı toplu üretimde görsel tekrarı olmasın
fails = 0
problems = []
all_word_counts = Counter()
per_puzzle_words = []
img_counts = []
flag_counts = 0
start = time.time()
for i in range(N):
    t0 = time.time()
    result = None
    for _ in range(5):
        result = generate_puzzle(wb, random.Random(), session_images=session_images)
        if result:
            break
    elapsed = time.time() - t0
    if not result:
        fails += 1
        print(f"#{i+1:2d}: FAIL | {elapsed:5.2f}s")
        continue

    slots, breaks, grid, image_assignments = result
    words = [''.join(grid[c] for c in s.cells()) for s in slots]

    # --- kural kontrolleri ---
    if not TEK_HARFLI_CEVAP and any(len(w) < 2 for w in words):
        problems.append((i + 1, 'tek harfli cevap'))
    # Her ipucu hücresinde ipucu olmalı (ipucusuz harf/boş ipucu hücresi kalmamalı)
    pj = puzzle_to_json(grid, slots, breaks, wb, image_assignments=image_assignments)
    bos = [(c['row'], c['col']) for c in pj['cells'] if not c['is_playable'] and not c.get('clues')
           and not c.get('clue_text') and not c.get('clue_image_url')]
    if bos and TEK_HARFLI_CEVAP:
        problems.append((i + 1, f'ipucusuz hücre: {bos}'))
    if len(set(words)) != len(words):
        problems.append((i + 1, 'aynı kelime iki kez'))
    bad = [(a, b) for k, a in enumerate(words) for b in words[k + 1:] if _prefix_conflict(a, {b})]
    if bad:
        problems.append((i + 1, f'benzer kelimeler: {bad[:2]}'))
    if any(w not in wb.clues_by_word for w in words):
        problems.append((i + 1, 'bankada olmayan kelime'))

    n_flag = sum(1 for v in image_assignments.values() if v['type'] == 'flag')
    if n_flag > 1:
        problems.append((i + 1, f'{n_flag} bayrak (en fazla 1 olmalı)'))
    per_puzzle_words.append(set(words))
    img_counts.append(len(image_assignments))
    flag_counts += n_flag
    all_word_counts.update(words)
    tek = sum(1 for w in words if len(w) == 1)
    print(f"#{i+1:2d}: OK   | {elapsed:5.2f}s | kelime: {len(words)} (tek harfli: {tek}) | bölme: {len(breaks)} | görsel (bayrak dahil): {len(image_assignments)} | bayrak: {n_flag}")

total_time = time.time() - start
ok = N - fails
anchors, usage, _img_usage = load_registry(tmp_xlsx)
print('\n=== ÖZET ===')
print(f'Başarı: {ok}/{N} ({100 * ok / N:.0f}%), ortalama {total_time / N:.2f} sn/bulmaca')
print(f'Kayıtlı benzersiz anchor çifti: {len(anchors)} (üretilen bulmaca: {ok}) -> tekrar yok: {len(anchors) == ok}')
if per_puzzle_words:
    uniq = len(all_word_counts)
    tot = sum(all_word_counts.values())
    print(f'Kullanılan farklı kelime: {uniq} / toplam kullanım {tot} (tekrar oranı: {100 * (1 - uniq / tot):.0f}%)')
print('Bulmaca başına görsel sayısı:', {k: img_counts.count(k) for k in sorted(set(img_counts))}, '| bayraklı bulmaca:', flag_counts, '/', len(img_counts))
print('Kural ihlali:', 'YOK' if not problems else problems)

shutil.rmtree(tmp_dir, ignore_errors=True)
