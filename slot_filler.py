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


def fill_grid(slots, word_bank, max_tries_per_slot=40, max_backtracks=20000):
    """Geri izlemeli arama (backtracking) ile ızgarayı doldurur.
    Dönüş: {(row,col): harf} sözlüğü, veya None (çözüm bulunamazsa)."""
    grid = {}
    used_words = set()
    backtrack_counter = [0]

    # Kesişim sayısına göre sırala (en çok kısıtlanan slot önce denenir - daha hızlı başarısız olur/bulur).
    def constrained_positions(slot):
        return {i: grid[c] for i, c in enumerate(slot.cells()) if c in grid}

    def most_constrained_unfilled(remaining):
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
        candidates = [w for w in candidates if w not in used_words]
        random.shuffle(candidates)

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
            slot.solved_word = word
            if backtrack(rest):
                return True

            used_words.discard(word)
            for c in placed:
                del grid[c]

        return False

    success = backtrack(list(slots))
    return grid if success else None
