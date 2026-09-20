"""Bulmaca üretiminin uçtan uca akışı: şablon -> TEK bir entegre kelime
doldurma (görsel/bayrak TERCİHLERİ dahil) -> sonuçtan görsel atamalarını
çıkarma. generate_puzzle() TEK giriş noktası - export_json.puzzle_to_json
ile birlikte kullanılır.

ÖNEMLİ TASARIM NOTU: Görsel/bayrak kelimeleri ASLA önceden zorla
yerleştirilmiyor (bu, ilk denemede %70'in üzerinde başarısızlığa yol
açıyordu - kesişimleri çözülemez hale getiriyordu). Bunun yerine, seçilen
birkaç kenar hücresi için doldurma algoritmasına "önce bunu dene, olmazsa
normal kelimeye geç" şeklinde bir TERCİH veriliyor (bkz. slot_filler.py'deki
preferred_words parametresi) - tek, tutarlı bir geri izlemeli (backtracking)
arama içinde. Böylece bir görsel/bayrak kelimesi işe yaramazsa arama
otomatik olarak normal bir kelimeye döner, bulmaca ASLA çözülemez hale
gelmez - sadece o hücrede görsel yerine metin ipucu kalır.
"""
from dynamic_template_v2 import generate_dynamic_slots_v2
from slot_filler import fill_grid
from anchor_registry import load_used_anchors, save_used_anchor

FLAG_CHANCE = 0.25       # bulmacaların ~%25'i bayraklı olsun
MAX_IMAGE_CELLS = 4      # bir bulmacada en fazla 4 görsel hücre (bayrak dahil) HEDEFLENİYOR


def eligible_single_slots(slots):
    """Görsel/bayrak KONULABİLECEK tek sorulu kenar hücrelerinin ipucunu veren
    slotları döner: (slot, o ipucunun göründüğü soru hücresi) çiftleri.
    - col0 marjini (her satırın ilk sağa-kelimesi)
    - row0 marjini (her sütunun ilk aşağı-kelimesi)
    - col6'daki tek sorulu kenar kırılması (row1'den sonraki aşağı-kelimeler)
    - row8'deki tek sorulu kenar kırılması (col1'den sonraki sağa-kelimeler)
    İç (çift sorulu) hücreler kesinlikle DAHIL EDİLMEZ.
    """
    eligible = []
    for s in slots:
        if s.direction == 'across' and s.start_col == 1:
            eligible.append((s, (s.start_row, 0)))
        elif s.direction == 'down' and s.start_row == 1:
            eligible.append((s, (0, s.start_col)))
        elif s.direction == 'down' and s.start_row > 1 and s.start_col == 6:
            eligible.append((s, (s.start_row - 1, 6)))
        elif s.direction == 'across' and s.start_col > 1 and s.start_row == 8:
            eligible.append((s, (8, s.start_col - 1)))
    return eligible


def _find_anchor_slots(slots):
    """(row1'in 6 harfli slotu, col1'in 8 harfli slotu) çiftini bulur."""
    row1_slot = next(s for s in slots if s.direction == 'across' and s.start_row == 1 and s.start_col == 1)
    col1_slot = next(s for s in slots if s.direction == 'down' and s.start_row == 1 and s.start_col == 1)
    return row1_slot, col1_slot


def generate_puzzle(word_bank, rng, max_tries_per_slot=80, max_backtracks=300000, outer_retries=40,
                     anchor_registry_path=None):
    """Başarılı olursa (slots, all_breaks, grid, image_assignments) döner.
    image_assignments: {(row,col): {'type': 'image'|'flag', 'url': str}} -
    export_json.puzzle_to_json'a doğrudan verilir.

    Anchor çifti (row1'in 6 harflisi + col1'in 8 harflisi) daha önce
    üretilmiş HİÇBİR bulmacada kullanılmamış olacak şekilde garanti edilir -
    bkz. anchor_registry.py (kayıt, kelime bankasıyla aynı Excel dosyasının
    'Uretilen_Bulmacalar' sayfasında tutulur). Başarılı her üretimden sonra
    bu ikili kalıcı kayda otomatik eklenir.

    Görsel/bayrak sayısı 0 ile MAX_IMAGE_CELLS arasında olabilir - hedef en
    yüksek sayı ama TERCİH mekanizması gereği gerçek sayı kesişimlere bağlı
    olarak daha düşük çıkabilir (asla puzzle'ı imkansız kılmaz).

    Tüm denemeler başarısız olursa None döner - çağıran taraf yeni bir rng
    ile (yeni bir şablonla) tekrar dener."""
    anchor_path = anchor_registry_path or word_bank.xlsx_path
    used_anchors = load_used_anchors(anchor_path)

    for _ in range(outer_retries):
        slots, all_breaks, row_b, col_b = generate_dynamic_slots_v2(rng)
        eligible = eligible_single_slots(slots)
        row1_slot, col1_slot = _find_anchor_slots(slots)
        candidates = list(eligible)
        rng.shuffle(candidates)

        preferred_words = {}
        target_cells = {}  # slot.id -> (cell, type)

        use_flag = rng.random() < FLAG_CHANCE and word_bank.flag_words_by_len
        idx = 0
        if use_flag and candidates:
            slot, cell = candidates[idx]
            preferred_words[slot.id] = 'flag'
            target_cells[slot.id] = (cell, 'flag')
            idx += 1

        remaining_cap = MAX_IMAGE_CELLS - (1 if use_flag else 0)
        for slot, cell in candidates[idx:idx + remaining_cap]:
            preferred_words[slot.id] = 'image'
            target_cells[slot.id] = (cell, 'image')

        grid = fill_grid(slots, word_bank, max_tries_per_slot=max_tries_per_slot,
                          max_backtracks=max_backtracks, preferred_words=preferred_words,
                          anchor_slot_ids=(row1_slot.id, col1_slot.id), used_anchor_pairs=used_anchors)
        if grid is None:
            continue

        # Hangi hedef slotlar GERÇEKTEN görsel/bayrak kelimeyle sonuçlandı -
        # tercih tutmamış olabilir, o zaman o hücrede normal metin kalır.
        image_assignments = {}
        for slot in slots:
            if slot.id not in target_cells:
                continue
            cell, typ = target_cells[slot.id]
            word = ''.join(grid[c] for c in slot.cells())
            if typ == 'flag' and word in word_bank.flag_words_by_len.get(len(word), []):
                image_assignments[cell] = {'type': 'flag', 'url': word_bank.flag_clue(word)}
            elif typ == 'image' and word in word_bank.image_words_by_len.get(len(word), []):
                image_assignments[cell] = {'type': 'image', 'url': word_bank.image_clue(word)}

        row1_word = ''.join(grid[c] for c in row1_slot.cells())
        col1_word = ''.join(grid[c] for c in col1_slot.cells())
        save_used_anchor(row1_word, col1_word, anchor_path)

        return slots, all_breaks, grid, image_assignments

    return None
