"""Kelime bankası: xlsx'ten yükleme, temizleme, uzunluk/pozisyon indeksleme.

'Tip' sütunu (opsiyonel, yoksa/boşsa hepsi 1 kabul edilir):
  1 (veya boş) = normal metin ipucusu
  2            = görsel ipucusu (Tanım/Soru sütununda bir görsel URL'si var)
  3            = bayrak ipucusu (Tanım/Soru sütununda bir bayrak görseli URL'si var)

Bir kelimenin hem Tip=1 hem Tip=2 satırı olabilir (aynı kelime için 2 ayrı
satır) - bulmacada bu kelime "tek sorulu kenar" bir hücreye denk gelirse
görsel tercih edilir, değilse (iç/çift sorulu hücreye denk gelirse) metin
kullanılır. Bayrak kelimeleri (Tip=3) SADECE bayrak olarak var - metin
karşılıkları yok, bu yüzden genel kelime havuzunda YER ALMAZLAR, sadece
özel bayrak yerleştirme adımında kullanılırlar (bkz. puzzle_pipeline.py).

NOT: Görsel ipucusu eklediğiniz bir kelimenin YANINDA en az bir metin
ipucusu (Tip=1) da bulundurmanız güvenlidir - metin karşılığı olmayan bir
kelime iç (çift sorulu) bir hücreye denk gelirse ipucu bulunamaz.
"""
import pandas as pd
import re
from collections import defaultdict


class WordBank:
    def __init__(self, xlsx_path):
        df = pd.read_excel(xlsx_path)
        # Sütun adları hem eski (Tanım / Soru, Cevap, Tip) hem yeni (soru,
        # cevap, tip - küçük harfli) biçimde gelebiliyor - ikisini de kabul et.
        rename_map = {}
        cols_lower = {c.lower().strip(): c for c in df.columns}
        if 'soru' in cols_lower and 'Tanım / Soru' not in df.columns:
            rename_map[cols_lower['soru']] = 'Tanım / Soru'
        if 'cevap' in cols_lower and 'Cevap' not in df.columns:
            rename_map[cols_lower['cevap']] = 'Cevap'
        if 'tip' in cols_lower and 'Tip' not in df.columns:
            rename_map[cols_lower['tip']] = 'Tip'
        if rename_map:
            df = df.rename(columns=rename_map)

        df = df.dropna(subset=['Cevap', 'Tanım / Soru'])
        df['Cevap'] = df['Cevap'].astype(str).str.strip().str.upper()
        df['Tanım / Soru'] = df['Tanım / Soru'].astype(str).str.strip()
        if 'Tip' in df.columns:
            df['Tip'] = pd.to_numeric(df['Tip'], errors='coerce').fillna(1).astype(int)
        else:
            df['Tip'] = 1
        # Sadece Türkçe harflerden oluşan, tek kelimelik cevapları al.
        df = df[df['Cevap'].str.match(r'^[A-ZÇĞİÖŞÜ]+$', na=False)]

        # word -> [{'value': metin_veya_url, 'tip': 1|2|3}, ...]
        self.clues_by_word = defaultdict(list)
        for _, row in df.iterrows():
            self.clues_by_word[row['Cevap']].append({'value': row['Tanım / Soru'], 'tip': int(row['Tip'])})

        # Genel doldurma havuzu: SADECE en az 1 metin (tip=1) ipucusu olan
        # kelimeler - bayrak-only ve (varsa) görsel-only kelimeler bu havuzda
        # YOK, çünkü iç/çift sorulu bir hücreye denk gelirlerse ipucu bulunamaz.
        text_words = {w for w, clues in self.clues_by_word.items() if any(c['tip'] == 1 for c in clues)}
        self.words_by_len = defaultdict(list)
        for w in text_words:
            self.words_by_len[len(w)].append(w)

        # Sadece bayrak (tip=3) kelimeler - özel bayrak yerleştirme adımı için ayrı havuz.
        flag_words = {w for w, clues in self.clues_by_word.items() if any(c['tip'] == 3 for c in clues)}
        self.flag_words_by_len = defaultdict(list)
        for w in flag_words:
            self.flag_words_by_len[len(w)].append(w)

        # Görsel (tip=2) ipucusu olan kelimeler - aktif görsel yerleştirme adımı için ayrı havuz.
        image_words = {w for w, clues in self.clues_by_word.items() if any(c['tip'] == 2 for c in clues)}
        self.image_words_by_len = defaultdict(list)
        for w in image_words:
            self.image_words_by_len[len(w)].append(w)

        # Bayrak/görsel kelimeler için de (length, pos, letter) indeksi - bunlar
        # genel havuzda OLMAYABİLİR (özellikle bayraklar hiç yok), o yüzden
        # kesişim-uyumlu aday ararken ayrı bir indekse ihtiyaç var.
        self._flag_pos_letter = self._build_pos_letter_index(flag_words)
        self._image_pos_letter = self._build_pos_letter_index(image_words)

        # (length, position, letter) -> [kelimeler] - hızlı kısıt araması için (genel havuzdan).
        self.by_len_pos_letter = defaultdict(list)
        for length, words in self.words_by_len.items():
            for w in words:
                for pos, letter in enumerate(w):
                    self.by_len_pos_letter[(length, pos, letter)].append(w)

    @staticmethod
    def _build_pos_letter_index(words):
        idx = defaultdict(list)
        for w in words:
            for pos, letter in enumerate(w):
                idx[(len(w), pos, letter)].append(w)
        return idx

    def _candidates_from(self, pool_by_len, pos_letter_index, length, constraints):
        if not constraints:
            return pool_by_len.get(length, [])
        keys = [(length, pos, letter) for pos, letter in constraints.items()]
        lists = [pos_letter_index.get(k, []) for k in keys]
        if not lists:
            return pool_by_len.get(length, [])
        lists.sort(key=len)
        result = set(lists[0])
        for lst in lists[1:]:
            result &= set(lst)
            if not result:
                return []
        return list(result)

    def candidates(self, length, constraints):
        """constraints: {pozisyon: harf} - o pozisyonlarda belirli harf isteyen kelimeleri döndürür."""
        return self._candidates_from(self.words_by_len, self.by_len_pos_letter, length, constraints)

    def flag_candidates(self, length, constraints):
        """Kesişim kısıtlarına uyan BAYRAK kelimelerini döner (tercih mekanizması için)."""
        return self._candidates_from(self.flag_words_by_len, self._flag_pos_letter, length, constraints)

    def image_candidates(self, length, constraints):
        """Kesişim kısıtlarına uyan GÖRSEL kelimelerini döner (tercih mekanizması için)."""
        return self._candidates_from(self.image_words_by_len, self._image_pos_letter, length, constraints)

    def random_clue(self, word):
        import random
        texts = [c['value'] for c in self.clues_by_word[word] if c['tip'] == 1]
        return random.choice(texts) if texts else None

    def shortest_clue(self, word, max_len=22):
        """Hücreye sığması için en kısa METİN ipucusunu seçer (görsel/bayrak asla dönmez)."""
        texts = sorted((c['value'] for c in self.clues_by_word[word] if c['tip'] == 1), key=len)
        if not texts:
            return None
        for t in texts:
            if len(t) <= max_len:
                return t
        return texts[0]

    def image_clue(self, word):
        """Bu kelimenin bir görsel (tip=2) ipucusu varsa URL'sini döner, yoksa None."""
        for c in self.clues_by_word[word]:
            if c['tip'] == 2:
                return c['value']
        return None

    def flag_clue(self, word):
        """Bu kelimenin bir bayrak (tip=3) ipucusu varsa URL'sini döner, yoksa None."""
        for c in self.clues_by_word[word]:
            if c['tip'] == 3:
                return c['value']
        return None
