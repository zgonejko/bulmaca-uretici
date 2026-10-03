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
import os
import random
import pandas as pd
from collections import defaultdict

# Kelime bankası varsayılan olarak bu dosyanın yanındaki bulmaca.xlsx'tir.
DEFAULT_XLSX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bulmaca.xlsx')

# True: tek harfli cevaplar (A, K, M, Y... ) kullanilir; satir/sutunda tek hucre kalan yerlerin
# de kendi ipucu olur (bankada tek harfli cevap olmali). False: tek harfli cevap yok, o ipucu hucreleri bos kalir.
TEK_HARFLI_CEVAP = True


class WordBank:
    def __init__(self, xlsx_path=DEFAULT_XLSX):
        self.xlsx_path = xlsx_path
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
        # Türkçe büyük harf: i -> İ, ı -> I (Python'un upper()'ı i'yi I yapar, bu yüzden küçük harfle
        # yazılmış cevaplar - örn. görsel satırları 'aplik' - yanlış harfli çıkardı ve metin ipucu satırlarıyla eşleşmezdi).
        df['Cevap'] = (df['Cevap'].astype(str).str.strip()
                       .str.replace('i', 'İ', regex=False).str.replace('ı', 'I', regex=False).str.upper())
        df['Tanım / Soru'] = df['Tanım / Soru'].astype(str).str.strip()
        if 'Tip' in df.columns:
            df['Tip'] = pd.to_numeric(df['Tip'], errors='coerce').fillna(1).astype(int)
        else:
            df['Tip'] = 1
        # Sadece Türkçe harflerden oluşan, tek kelimelik cevapları al.
        df = df[df['Cevap'].str.match(r'^[A-ZÇĞİÖŞÜ]+$', na=False)]
        if not TEK_HARFLI_CEVAP:
            df = df[df['Cevap'].str.len() >= 2]

        # word -> [{'value': metin_veya_url, 'tip': 1|2|3}, ...]
        # Tip 2 (görsel) ve tip 3 (eski bayrak tipi) AYNI şeydir: görsel ipucu. Görselin BAYRAK olup
        # olmadığı adresinden anlaşılır ('/flags/' klasörü) - Excel'de bayraklar da tip 2 yazılabilir.
        self.clues_by_word = defaultdict(list)
        for _, row in df.iterrows():
            tip = int(row['Tip'])
            clue = {'value': row['Tanım / Soru'], 'tip': 2 if tip == 3 else tip}
            if clue['tip'] == 2:
                clue['is_flag'] = tip == 3 or '/flags/' in str(row['Tanım / Soru']).lower()
            self.clues_by_word[row['Cevap']].append(clue)

        # Genel doldurma havuzu: SADECE en az 1 metin (tip=1) ipucusu olan
        # kelimeler - bayrak-only ve (varsa) görsel-only kelimeler bu havuzda
        # YOK, çünkü iç/çift sorulu bir hücreye denk gelirlerse ipucu bulunamaz.
        text_words = {w for w, clues in self.clues_by_word.items() if any(c['tip'] == 1 for c in clues)}
        self.words_by_len = defaultdict(list)
        for w in text_words:
            self.words_by_len[len(w)].append(w)

        # Bayrak görselli kelimeler (adresi /flags/ içeren görseller) - bayrak yerleştirme adımı için ayrı havuz.
        flag_words = {w for w, clues in self.clues_by_word.items()
                      if any(c['tip'] == 2 and c.get('is_flag') for c in clues)}
        self.flag_words_by_len = defaultdict(list)
        for w in flag_words:
            self.flag_words_by_len[len(w)].append(w)

        # Bayrak OLMAYAN görsel ipuçlu kelimeler - görsel yerleştirme adımı için ayrı havuz.
        image_words = {w for w, clues in self.clues_by_word.items()
                       if any(c['tip'] == 2 and not c.get('is_flag') for c in clues)}
        self.image_words_by_len = defaultdict(list)
        for w in image_words:
            self.image_words_by_len[len(w)].append(w)

        # Bayrak/görsel kelimeler için de (length, pos, letter) indeksi - bunlar
        # genel havuzda OLMAYABİLİR (özellikle bayraklar hiç yok), o yüzden
        # kesişim-uyumlu aday ararken ayrı bir indekse ihtiyaç var.
        self._set_cache = {}
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

    def _candidate_set_from(self, pool_by_len, pos_letter_index, length, constraints):
        """_candidates_from'un KÜME döndüren hızlı hali. Kümeler bir kez hesaplanıp önbelleğe alınır;
        kesişimler (&) ve çıkarmalar (-) Python döngüsü yerine C hızında yapılır. DÖNEN KÜMEYİ DEĞİŞTİRMEYİN."""
        cache = self._set_cache.setdefault(id(pool_by_len), {})
        if not constraints:
            key = ('all', length)
            r = cache.get(key)
            if r is None:
                r = cache[key] = frozenset(pool_by_len.get(length, ()))
            return r
        sets = []
        for pos, letter in constraints.items():
            k = (length, pos, letter)
            r = cache.get(k)
            if r is None:
                r = cache[k] = frozenset(pos_letter_index.get(k, ()))
            if not r:
                return frozenset()
            sets.append(r)
        sets.sort(key=len)
        result = sets[0]
        for other in sets[1:]:
            result = result & other
            if not result:
                return frozenset()
        return result

    def candidate_set(self, length, constraints):
        return self._candidate_set_from(self.words_by_len, self.by_len_pos_letter, length, constraints)

    def flag_candidate_set(self, length, constraints):
        return self._candidate_set_from(self.flag_words_by_len, self._flag_pos_letter, length, constraints)

    def image_candidate_set(self, length, constraints):
        return self._candidate_set_from(self.image_words_by_len, self._image_pos_letter, length, constraints)

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
        texts = [c['value'] for c in self.clues_by_word[word] if c['tip'] == 1]
        return random.choice(texts) if texts else None

    def shortest_clue(self, word, max_len=22):
        """Hücreye sığan (max_len karakter veya daha kısa) METİN ipuçları arasından
        RASTGELE birini seçer; hiçbiri sığmıyorsa en kısasını döner. (Görsel/bayrak
        asla dönmez.) Böylece aynı kelime farklı bulmacalarda farklı ipuçlarıyla gelir."""
        texts = [c['value'] for c in self.clues_by_word[word] if c['tip'] == 1]
        if not texts:
            return None
        fitting = [t for t in texts if len(t) <= max_len]
        if fitting:
            return random.choice(fitting)
        return min(texts, key=len)

    def image_clue(self, word):
        """Bu kelimenin bir görsel (tip=2) ipucusu varsa URL'sini döner, yoksa None."""
        for c in self.clues_by_word[word]:
            if c['tip'] == 2 and not c.get('is_flag'):
                return c['value']
        return None

    def flag_clue(self, word):
        """Bu kelimenin bir bayrak görseli varsa URL'sini döner, yoksa None."""
        for c in self.clues_by_word[word]:
            if c['tip'] == 2 and c.get('is_flag'):
                return c['value']
        return None
