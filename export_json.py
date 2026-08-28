"""Üretilen bulmacayı, uygulamanın (Flutter) Puzzle modeliyle bire bir
eşleşen JSON formatına çevirir. Bu, üretici ile uygulama arasındaki
TEK bağlantı noktasıdır - uygulama bu formatı okur, nasıl üretildiğini bilmez."""
import json
import uuid


def puzzle_to_json(grid, slots, breaks, word_bank, rows=9, cols=7):
    cells = []

    for r in range(rows):
        for c in range(cols):
            if r == 0 and c == 0:
                continue  # sol üst köşe boş
            cells.append({'row': r, 'col': c, 'is_playable': False, 'clue_text': None, 'clue_image_url': None})

    cell_index = {(c['row'], c['col']): i for i, c in enumerate(cells)}

    # İç kısımdaki harf hücreleri + çözüm harfleri
    for (r, c), letter in grid.items():
        idx = cell_index[(r, c)]
        cells[idx]['is_playable'] = True
        cells[idx]['solution_letter'] = letter

    # Üst satır (row0) ipuçları: her sütunun İLK aşağı-segmentinin çözülen
    # kelimesinden geliyor - ayrı bir kaynağa gerek yok, aynı mekanizma.
    for c in range(1, cols):
        first_down = next((s for s in slots if s.direction == 'down' and s.start_col == c and s.start_row == 1), None)
        if first_down:
            word = ''.join(grid[cc] for cc in first_down.cells())
            idx = cell_index[(0, c)]
            cells[idx]['clue_text'] = word_bank.random_clue(word)

    # Sol sütun (col0) ipuçları: her satırın İLK sağa-segmentinin çözülen
    # kelimesinden geliyor - aynı şekilde.
    for r in range(1, rows):
        first_across = next((s for s in slots if s.direction == 'across' and s.start_row == r and s.start_col == 1), None)
        if first_across:
            word = ''.join(grid[cc] for cc in first_across.cells())
            idx = cell_index[(r, 0)]
            cells[idx]['clue_text'] = word_bank.random_clue(word)

    # İç kısımdaki bölme/ipucu hücreleri - hangi yönde kaç ipucu olduğunu belirle
    for (r, c) in breaks:
        idx = cell_index[(r, c)]
        clue_texts = []
        # Bu hücreden sağa doğru yeni bir kelime başlıyor mu?
        for s in slots:
            if s.direction == 'across' and s.start_row == r and s.start_col == c + 1:
                word = ''.join(grid[cc] for cc in s.cells())
                clue_texts.append({'direction': 'right', 'text': word_bank.random_clue(word)})
        # Bu hücreden aşağı doğru yeni bir kelime başlıyor mu?
        for s in slots:
            if s.direction == 'down' and s.start_col == c and s.start_row == r + 1:
                word = ''.join(grid[cc] for cc in s.cells())
                clue_texts.append({'direction': 'down', 'text': word_bank.random_clue(word)})
        cells[idx]['is_playable'] = False
        cells[idx]['clues'] = clue_texts
        cells[idx].pop('clue_text', None)
        cells[idx].pop('clue_image_url', None)

    # Harf akışı: tüm slotlardaki harflerin okuma sırasına göre birleşimi
    # (uygulamadaki 5'lik panel mantığı için sıralı liste).
    letter_flow = []
    for s in slots:
        for cell in s.cells():
            letter = grid.get(cell)
            if letter and cell not in [tuple(x) for x in []]:  # basitleştirilmiş, tekilleştirme aşağıda
                pass
    seen = set()
    letter_flow = []
    for (r, c), letter in grid.items():
        pass
    # Basitleştirilmiş akış: hücreleri satır-sütun sırasına göre diz.
    for (r, c) in sorted(grid.keys()):
        letter_flow.append(grid[(r, c)])

    puzzle = {
        'id': str(uuid.uuid4()),
        'rows': rows,
        'cols': cols,
        'cells': cells,
        'letter_flow': letter_flow,
        'ai_difficulty': None,  # zorluk skoru henüz atanmadı (Bölüm 8 - kullanıcı verisiyle güncellenecek)
    }
    return puzzle


if __name__ == '__main__':
    import sys, random
    sys.path.insert(0, '.')
    from word_bank import WordBank
    from slot_filler import fill_grid
    from dynamic_template_v2 import generate_dynamic_slots_v2

    wb = WordBank('/mnt/user-data/uploads/Kitap_Kisa_Cevaplar_Basta_-_Kopya.xlsx')
    grid = None
    for _ in range(25):
        rng = random.Random()
        slots, breaks, row_b, col_b = generate_dynamic_slots_v2(rng)
        grid = fill_grid(slots, wb, max_tries_per_slot=50, max_backtracks=30000)
        if grid:
            break

    puzzle_json = puzzle_to_json(grid, slots, breaks, wb)
    with open('/home/claude/puzzle-generator/sample_puzzle.json', 'w', encoding='utf-8') as f:
        json.dump(puzzle_json, f, ensure_ascii=False, indent=2)
    print('sample_puzzle.json yazıldı')
    print(f"Toplam hücre: {len(puzzle_json['cells'])}, harf akışı uzunluğu: {len(puzzle_json['letter_flow'])}")
