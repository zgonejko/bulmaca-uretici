"""Üretilen bulmacayı, uygulamanın (Flutter) Puzzle modeliyle bire bir
eşleşen JSON formatına çevirir. Bu, üretici ile uygulama arasındaki
TEK bağlantı noktasıdır - uygulama bu formatı okur, nasıl üretildiğini bilmez."""
import json
import uuid


def puzzle_to_json(grid, slots, breaks, word_bank, rows=9, cols=7, image_assignments=None):
    image_assignments = image_assignments or {}
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
    # Görsel/bayrak atanmışsa metin yerine clue_image_url kullanılır.
    for c in range(1, cols):
        first_down = next((s for s in slots if s.direction == 'down' and s.start_col == c and s.start_row == 1), None)
        if first_down:
            word = ''.join(grid[cc] for cc in first_down.cells())
            idx = cell_index[(0, c)]
            assign = image_assignments.get((0, c))
            if assign:
                cells[idx]['clue_image_url'] = assign['url']
                cells[idx]['is_flag'] = assign['type'] == 'flag'
            else:
                cells[idx]['clue_text'] = word_bank.shortest_clue(word)

    # Sol sütun (col0) ipuçları: her satırın İLK sağa-segmentinin çözülen
    # kelimesinden geliyor - aynı şekilde.
    for r in range(1, rows):
        first_across = next((s for s in slots if s.direction == 'across' and s.start_row == r and s.start_col == 1), None)
        if first_across:
            word = ''.join(grid[cc] for cc in first_across.cells())
            idx = cell_index[(r, 0)]
            assign = image_assignments.get((r, 0))
            if assign:
                cells[idx]['clue_image_url'] = assign['url']
                cells[idx]['is_flag'] = assign['type'] == 'flag'
            else:
                cells[idx]['clue_text'] = word_bank.shortest_clue(word)

    # İç kısımdaki bölme/ipucu hücreleri - hangi yönde kaç ipucu olduğunu belirle.
    # NOT: Bu hücrelerden yalnızca TEK yönlü olanlar (col6/row8 kenar
    # kırılmaları) görsel/bayrak alabilir - çift sorulu (iç) hücrelere ASLA
    # görsel atanmaz (image_assignments zaten sadece eligible_single_slots'tan
    # doldurulduğu için buna gerek kalmadan doğru çalışıyor).
    for (r, c) in breaks:
        idx = cell_index[(r, c)]
        clue_texts = []
        assign = image_assignments.get((r, c))
        # Bu hücreden sağa doğru yeni bir kelime başlıyor mu?
        for s in slots:
            if s.direction == 'across' and s.start_row == r and s.start_col == c + 1:
                word = ''.join(grid[cc] for cc in s.cells())
                if assign:
                    clue_texts.append({'direction': 'right', 'text': None, 'image_url': assign['url'], 'is_flag': assign['type'] == 'flag'})
                else:
                    clue_texts.append({'direction': 'right', 'text': word_bank.shortest_clue(word)})
        # Bu hücreden aşağı doğru yeni bir kelime başlıyor mu?
        for s in slots:
            if s.direction == 'down' and s.start_col == c and s.start_row == r + 1:
                word = ''.join(grid[cc] for cc in s.cells())
                if assign:
                    clue_texts.append({'direction': 'down', 'text': None, 'image_url': assign['url'], 'is_flag': assign['type'] == 'flag'})
                else:
                    clue_texts.append({'direction': 'down', 'text': word_bank.shortest_clue(word)})
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
    import os, random
    from word_bank import WordBank, DEFAULT_XLSX
    from puzzle_pipeline import generate_puzzle

    wb = WordBank(DEFAULT_XLSX)
    result = None
    for _ in range(25):
        rng = random.Random()
        result = generate_puzzle(wb, rng)
        if result:
            break

    slots, breaks, grid, image_assignments = result
    puzzle_json = puzzle_to_json(grid, slots, breaks, wb, image_assignments=image_assignments)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_puzzle.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(puzzle_json, f, ensure_ascii=False, indent=2)
    print(f'{out_path} yazıldı')
    print(f"Toplam hücre: {len(puzzle_json['cells'])}, görsel/bayrak hücre sayısı: {len(image_assignments)}")
