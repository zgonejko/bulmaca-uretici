"""Genel amaçlı slot tabanlı çengel bulmaca doldurma motoru.
Herhangi bir ızgara şablonunu (slot listesini) gerçek kelime bankasından
kelimelerle doldurur - kesişen kısıtları (ortak hücreler) çözerek."""
import random


class Slot:
    def __init__(self, slot_id, direction, start_row, start_col, length):
        self.id = slot_id
        self.direction = direction  # 'across' veya 'down'
        self.start_row = start_row
        self.start_col = start_col
        self.length = length

    def cells(self):
        if self.direction == 'across':
            return [(self.start_row, self.start_col + i) for i in range(self.length)]
        else:
            return [(self.start_row + i, self.start_col) for i in range(self.length)]


def _prefix_conflict(word, used_words):
    """Aynı bulmacada anlamca/kökence çok benzer kelimelerin (örn. AKLANMA/
    AKLANMAK, DESTAN/DESTANSI) birlikte kullanılmasını engeller. Kelimenin
    uzunluğuna göre bir önek uzunluğu belirlenir (8->5, 7->4, 6->3, aşağı
    doğru aynı oranda azalarak - 5 ve altı kelimelerde önek çok kısa/
    anlamsız kalacağından kontrol devre dışı kalır).

    Kontrol SİMETRİKTİR: iki kelimeden HANGİSİNİN eşiği (kendi uzunluğuna
    göre) diğerinin aynı uzunluktaki önekiyle eşleşirse çakışma sayılır -
    tek yönlü olsaydı, önce uzun sonra kısa bir kelime eklendiğinde (örn.
    önce İRADE sonra İRİS) kısa kelimenin düşük eşiği devreye girip kontrolü
    atlayabilirdi."""
    def threshold(w):
        n = len(w) - 3
        return n if n >= 2 else None

    n_word = threshold(word)
    for w in used_words:
        if n_word is not None and len(w) >= n_word and w[:n_word] == word[:n_word]:
            return True
        n_w = threshold(w)
        if n_w is not None and len(word) >= n_w and word[:n_w] == w[:n_w]:
            return True
    return False


def fill_grid(slots, word_bank, max_tries_per_slot=40, max_backtracks=20000,
              initial_grid=None, initial_used_words=None, preferred_words=None,
              anchor_slot_ids=None, used_anchor_pairs=None):
    """Geri izlemeli arama (backtracking) ile ızgarayı doldurur.
    initial_grid/initial_used_words verilirse (örn. önceden yerleştirilmiş bir
    bayrak kelimesi), doldurma bu hazır harflerle kısıtlanarak devam eder -
    'slots' listesine önceden yerleştirilen slotu DAHIL ETMEYİN.

    preferred_words: {slot.id: 'flag'|'image'} - bu slotlar çözülürken önce
    ilgili havuzdan (bayrak/görsel) kesişime uyan kelimeler denenir, UYMAZSA
    normal kelime havuzuna sorunsuzca geri dönülür - yani bu bir ZORLAMA
    DEĞİL, sadece bir TERCİH SIRASI. Böylece bir görsel/bayrak kelimesi bir
    yerde işe yaramazsa, geri izleme (backtracking) bunu otomatik olarak
    normal bir kelimeyle değiştirir, bulmaca asla 'çözülemez' hale gelmez.

    anchor_slot_ids: (row1_slot.id, col1_slot.id) - bulmacanın 'anchor'
    çiftini oluşturan iki slot. used_anchor_pairs: {(row1_kelime, col1_kelime), ...}
    - bu ikili daha önce ÜRETİLMİŞ bulmacalarda kullanıldıysa, arama bu
    kombinasyonu bir kesişim çakışması gibi görüp otomatik olarak farklı bir
    kelime dener - anchor ikilisi kalıcı olarak asla tekrar üretilmez.

    Dönüş: {(row,col): harf} sözlüğü, veya None (çözüm bulunamazsa)."""
    grid = dict(initial_grid) if initial_grid else {}
    used_words = set(initial_used_words) if initial_used_words else set()
    preferred_words = preferred_words or {}
    used_anchor_pairs = used_anchor_pairs or set()
    anchor_a, anchor_b = anchor_slot_ids if anchor_slot_ids else (None, None)
    solved_word_by_slot = {}
    backtrack_counter = [0]

    # Kesişim sayısına göre sırala (en çok kısıtlanan slot önce denenir - daha hızlı başarısız olur/bulur).
    def constrained_positions(slot):
        return {i: grid[c] for i, c in enumerate(slot.cells()) if c in grid}

    def most_constrained_unfilled(remaining):
        # Tercih edilen (görsel/bayrak) slotlar varsa ÖNCE onları çözmeyi dene -
        # kısıtlar henüz gevşekken (az kesişim kilitlenmişken) uygun bir görsel/
        # bayrak kelime bulma şansı en yüksek oluyor. Yine de TAM backtracking
        # içinde olduğu için, bu seçim sonradan bulmacayı çözülemez kılarsa
        # otomatik olarak geri alınıp başka bir kelime (görsel ya da normal)
        # denenir - yani bu bir zorlama değil, sadece bir DENEME SIRASI.
        preferred_remaining = [s for s in remaining if s.id in preferred_words]
        if preferred_remaining:
            return preferred_remaining[0]
        # Basit sezgisel: en uzun slotlardan başla (daha az aday olduğu için erken elenir).
        return max(remaining, key=lambda s: (len(constrained_positions(s)), -word_count(s)))

    def word_count(slot):
        return len(word_bank.words_by_len.get(slot.length, []))

    def backtrack(remaining):
        if backtrack_counter[0] > max_backtracks:
            return False
        if not remaining:
            return True
        slot = most_constrained_unfilled(remaining)
        rest = [s for s in remaining if s is not slot]

        constraints = constrained_positions(slot)
        candidates = word_bank.candidates(slot.length, constraints)
        candidates = [w for w in candidates if w not in used_words and not _prefix_conflict(w, used_words)]
        random.shuffle(candidates)

        # Bu slot için bir tercih (görsel/bayrak) belirtilmişse, ilgili
        # havuzdan kesişime uyan kelimeleri bul ve listenin BAŞINA koy - önce
        # onlar denensin, ama uymazlarsa (ya da hiç yoksa) normal adaylara
        # sorunsuzca devam edilsin.
        pref_type = preferred_words.get(slot.id)
        if pref_type == 'flag':
            preferred_valid = [w for w in word_bank.flag_candidates(slot.length, constraints)
                                if w not in used_words and not _prefix_conflict(w, used_words)]
            candidates = preferred_valid + [w for w in candidates if w not in preferred_valid]
        elif pref_type == 'image':
            preferred_valid = [w for w in word_bank.image_candidates(slot.length, constraints)
                                if w not in used_words and not _prefix_conflict(w, used_words)]
            candidates = preferred_valid + [w for w in candidates if w not in preferred_valid]

        # Anchor çifti kısıtı: bu slot anchor'lardan biriyse VE diğeri zaten
        # çözülmüşse, o ikiliyi daha önce üretilmiş bir bulmacayla aynı
        # yapacak adayları ele - böylece aynı anchor çifti bir daha asla
        # üretilmiyor (bkz. fonksiyon docstring'i).
        if used_anchor_pairs and slot.id in (anchor_a, anchor_b):
            other_id = anchor_b if slot.id == anchor_a else anchor_a
            other_word = solved_word_by_slot.get(other_id)
            if other_word is not None:
                def _makes_used_pair(w, _slot_id=slot.id, _other=other_word):
                    pair = (w, _other) if _slot_id == anchor_a else (_other, w)
                    return pair in used_anchor_pairs
                candidates = [w for w in candidates if not _makes_used_pair(w)]

        for word in candidates[:max_tries_per_slot]:
            backtrack_counter[0] += 1
            if backtrack_counter[0] > max_backtracks:
                return False

            cells = slot.cells()
            placed = []
            conflict = False
            for i, c in enumerate(cells):
                if c in grid:
                    if grid[c] != word[i]:
                        conflict = True
                        break
                else:
                    grid[c] = word[i]
                    placed.append(c)
            if conflict:
                for c in placed:
                    del grid[c]
                continue

            used_words.add(word)
            solved_word_by_slot[slot.id] = word
            slot.solved_word = word
            if backtrack(rest):
                return True

            used_words.discard(word)
            del solved_word_by_slot[slot.id]
            for c in placed:
                del grid[c]

        return False

    success = backtrack(list(slots))
    return grid if success else None
