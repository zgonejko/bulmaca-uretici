import sys, random
sys.path.insert(0, '/home/claude/puzzle-generator')
from word_bank import WordBank
from slot_filler import fill_grid
from dynamic_template import generate_dynamic_slots

wb = WordBank('/mnt/user-data/uploads/Kitap_Kisa_Cevaplar_Basta_-_Kopya.xlsx')

def generate_one_puzzle(max_template_tries=25):
    for attempt in range(max_template_tries):
        rng = random.Random()
        slots, break_cells = generate_dynamic_slots(rng)
        grid = fill_grid(slots, wb, max_tries_per_slot=50, max_backtracks=30000)
        if grid is not None:
            return grid, slots, break_cells, attempt + 1
    return None, None, None, max_template_tries

grid, slots, break_cells, tries = generate_one_puzzle()

if grid is None:
    print(f"{tries} şablon denemesinde çözüm bulunamadı.")
else:
    print(f"BAŞARILI! ({tries}. şablon denemesinde çözüldü)\n")
    print(f"Toplam slot (kelime) sayısı: {len(slots)}")
    print(f"İç kısımdaki bölme/ipucu hücresi sayısı: {len(break_cells)}\n")

    # Izgarayı yazdır (9 satır x 7 sütun: row0=üst ipucu satırı, col0=sol ipucu sütunu)
    for r in range(9):
        line = ''
        for c in range(7):
            if r == 0 and c == 0:
                line += '  '
            elif r == 0:
                line += '^ '  # üst ipucu (sütun başlığı)
            elif c == 0:
                line += '> '  # sol ipucu (satır başlığı)
            elif (r, c) in break_cells:
                line += '# '  # iç kısımda dinamik ipucu hücresi
            else:
                line += grid.get((r, c), '.') + ' '
        print(line)

    print(f"\nÖrnek slotlar ve kelimeler:")
    for s in slots[:8]:
        word = ''.join(grid[c] for c in s.cells())
        clue = wb.random_clue(word)
        print(f"  {s.direction:6s} ({s.length} harf) satır{s.start_row} sütun{s.start_col}: {word} — {clue}")
