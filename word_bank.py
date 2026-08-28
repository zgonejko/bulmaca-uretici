"""Kelime bankası: xlsx'ten yükleme, temizleme, uzunluk/pozisyon indeksleme."""
import pandas as pd
import re
from collections import defaultdict


class WordBank:
    def __init__(self, xlsx_path):
        df = pd.read_excel(xlsx_path)
        df = df.dropna(subset=['Cevap', 'Tanım / Soru'])
        df['Cevap'] = df['Cevap'].astype(str).str.strip().str.upper()
        df['Tanım / Soru'] = df['Tanım / Soru'].astype(str).str.strip()
        # Sadece Türkçe harflerden oluşan, tek kelimelik cevapları al.
        df = df[df['Cevap'].str.match(r'^[A-ZÇĞİÖŞÜ]+$', na=False)]

        # word -> [olası ipuçları]
        self.clues_by_word = defaultdict(list)
        for _, row in df.iterrows():
            self.clues_by_word[row['Cevap']].append(row['Tanım / Soru'])

        self.words_by_len = defaultdict(list)
        for w in self.clues_by_word:
            self.words_by_len[len(w)].append(w)

        # (length, position, letter) -> [kelimeler] - hızlı kısıt araması için
        self.by_len_pos_letter = defaultdict(list)
        for length, words in self.words_by_len.items():
            for w in words:
                for pos, letter in enumerate(w):
                    self.by_len_pos_letter[(length, pos, letter)].append(w)

    def candidates(self, length, constraints):
        """constraints: {pozisyon: harf} - o pozisyonlarda belirli harf isteyen kelimeleri döndürür."""
        if not constraints:
            return self.words_by_len.get(length, [])
        # En kısıtlayıcı (en az sonuç veren) pozisyondan başla.
        keys = [(length, pos, letter) for pos, letter in constraints.items()]
        lists = [self.by_len_pos_letter.get(k, []) for k in keys]
        if not lists:
            return self.words_by_len.get(length, [])
        lists.sort(key=len)
        result = set(lists[0])
        for lst in lists[1:]:
            result &= set(lst)
            if not result:
                return []
        return list(result)

    def random_clue(self, word):
        import random
        return random.choice(self.clues_by_word[word])

    def shortest_clue(self, word, max_len=22):
        """Hücreye sığması için en kısa ipucunu seçer (mümkünse max_len altında)."""
        clues = self.clues_by_word[word]
        clues_sorted = sorted(clues, key=len)
        for c in clues_sorted:
            if len(c) <= max_len:
                return c
        return clues_sorted[0]  # hiçbiri kısa değilse en kısasını yine de döndür
