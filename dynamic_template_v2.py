"""9x7 şablon - v2: bölme noktaları her zaman HEM satırı HEM sütunu aynı anda
böler (gerçek çengel bulmaca mantığı). Sadece en alt satır/en sağ sütuna denk
gelen bölmeler tek yönlü kalır (o yönde devam edecek hücre kalmadığı için)."""
from slot_filler import Slot


def _segment_lengths(breaks_sorted, total):
    segs = []
    prev = 1
    for b in breaks_sorted:
        if b > prev:
            segs.append((prev, b - 1))
        prev = b + 1
    if prev <= total:
        segs.append((prev, total))
    return segs


def generate_dynamic_slots_v2(rng, num_breaks_range=(4, 8)):
    row_breaks = {r: set() for r in range(1, 9)}   # satır r içinde hangi sütunlarda bölme var
    col_breaks = {c: set() for c in range(1, 7)}   # sütun c içinde hangi satırlarda bölme var
    all_breaks = set()

    target = rng.randint(*num_breaks_range)
    candidates = [(r, c) for r in range(2, 9) for c in range(2, 7) if not (r == 8 and c == 6)]
    rng.shuffle(candidates)

    for (r, c) in candidates:
        if len(all_breaks) >= target:
            break
        # İki bölme noktası bitişik olamaz (aralarında en az 1 harf hücresi kalmalı),
        # yoksa biri diğerinin ipucu vereceği hücreyi de bölme yapıp boşa çıkarır.
        if any((r, c + 1) in all_breaks or (r, c - 1) in all_breaks for _ in [0]):
            continue
        if any((r + 1, c) in all_breaks or (r - 1, c) in all_breaks for _ in [0]):
            continue
        row_segs = _segment_lengths(sorted(row_breaks[r] | {c}), 6)
        col_segs = _segment_lengths(sorted(col_breaks[c] | {r}), 8)
        if all(e - s + 1 >= 2 for s, e in row_segs) and all(e - s + 1 >= 2 for s, e in col_segs):
            row_breaks[r].add(c)
            col_breaks[c].add(r)
            all_breaks.add((r, c))

    slots = []
    sid = 0
    for r in range(1, 9):
        for (s, e) in _segment_lengths(sorted(row_breaks[r]), 6):
            slots.append(Slot(f'A{sid}', 'across', r, s, e - s + 1)); sid += 1
    for c in range(1, 7):
        for (s, e) in _segment_lengths(sorted(col_breaks[c]), 8):
            slots.append(Slot(f'D{sid}', 'down', s, c, e - s + 1)); sid += 1

    return slots, all_breaks, row_breaks, col_breaks
