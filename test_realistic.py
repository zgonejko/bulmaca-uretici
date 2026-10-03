"""Gerçekçi (değişken uzunluklu, kesişen) bir şablonu gerçek kelime bankasıyla doldurma testi."""
from word_bank import WordBank, DEFAULT_XLSX
from slot_filler import Slot, fill_grid

wb = WordBank(DEFAULT_XLSX)

# Küçük, gerçekçi bir çengel bulmaca şablonu: kesişen, değişken uzunlukta kelimeler.
# (row, col) 0-indexli. Izgara 8x8, birkaç kesişen slot.
slots = [
    Slot('A1', 'across', 0, 0, 6),
    Slot('A2', 'across', 2, 1, 5),
    Slot('A3', 'across', 4, 0, 4),
    Slot('A4', 'across', 6, 2, 5),
    Slot('D1', 'down', 0, 0, 5),
    Slot('D2', 'down', 0, 3, 6),
    Slot('D3', 'down', 2, 1, 4),
    Slot('D4', 'down', 2, 5, 5),
]

grid = fill_grid(slots, wb, max_tries_per_slot=60, max_backtracks=50000)

if grid is None:
    print("Çözüm bulunamadı.")
else:
    print("BAŞARILI! Izgara dolduruldu.\n")
    rows = max(r for r, c in grid) + 1
    cols = max(c for r, c in grid) + 1
    for r in range(rows):
        line = ''
        for c in range(cols):
            line += grid.get((r, c), '·') + ' '
        print(line)

    print("\nSlot -> Kelime -> Örnek ipucu:")
    for s in slots:
        word = ''.join(grid[c] for c in s.cells())
        clue = wb.random_clue(word)
        print(f"  {s.id} ({s.direction}, {s.length} harf): {word} — İpucu: {clue}")
