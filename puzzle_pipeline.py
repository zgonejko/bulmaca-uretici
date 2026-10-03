"""Bulmaca üretiminin uçtan uca akışı: şablon -> kelime doldurma (görsel/bayrak hedefiyle) -> anchor kaydı.
generate_puzzle() TEK giriş noktası - export_json.puzzle_to_json ile birlikte kullanılır.

GÖRSEL/BAYRAK TASARIMI: Hedef (her bulmacada 4-5 görsel; %20 olasılıkla bunlardan biri bayrak) kelime
doldurma SIRASINDA garanti edilir, sonradan eklenmez: çözücü hangi kenar hücrelerinin görselli olacağını
kendisi seçer, görsele ulaşılamayacak yolları erken bırakır (bkz. slot_filler.fill_grid, image_goal).
Hedefe STAGE_ATTEMPTS denemede ulaşılamazsa hedef kademeli gevşetilir (önce bayrak şartı, sonra görsel sayısı
birer birer azalır) - bulmaca üretimi asla takılıp kalmaz.
"""
import time
from collections import Counter

from dynamic_template_v2 import generate_dynamic_slots_v2
from slot_filler import fill_grid, max_independent_count
from anchor_registry import load_registry, save_used_anchor

FLAG_CHANCE = 0.2             # bulmacaların ~5'te 1'inde (4-6 bulmacadan birinde) tam 1 bayrak; diğerlerinde hiç
MIN_IMAGE_CELLS = 4           # her bulmacada hedef görsel sayısı (varsa bayrak dahil): 4 ile 5 arasında
MAX_IMAGE_CELLS = 5
STAGE_ATTEMPTS = 250          # bir hedef kademesi için en fazla bu kadar deneme yap, sonra hedefi gevşet
FLAG_ATTEMPTS = 2500          # bayraklı kademe için deneme sayısı: denemeler çok ucuz (~0.01 sn) ama başarı oranı
                              # düşük (~%0.3); bayrağı boşuna elemek istemiyoruz. Süre yerine DENEME sayısı
                              # kullanılır ki yavaş bilgisayarda hedef boşuna gevşemesin.
REST_PUZZLES = 5                # bir görsel çıktıktan sonra, aynı toplu üretimde sonraki bu kadar bulmacada çıkmaz (dinlenme)
NO_ADJACENT_IMAGES = True       # True: görselli kutular yan yana / alt alta (kenar paylaşarak) olmaz. Kapatmak üretimi hızlandırır.
LONG_IMAGE_CHANCE = 0.5          # bulmacaların bu kadarında iskelet kelimesi (6 veya 8 harfli) görselli olur (baştan sabitlenir)
MAX_SHORT_IMAGES = 1            # iki harfli (AT, ET gibi) görselli kelime bir bulmacada en fazla bu kadar (None: sınırsız, daha hızlı)
GOAL_BACKTRACKS = 150         # görsel hedefli tek denemenin bütçesi (kısa denemeler + çok yeniden deneme daha verimli)


class SessionMemory:
    """Bir toplu üretimin (tek 'Üret' tıklaması) hafızası: hangi görsel/bayrak kaç kez ve en son hangi bulmacada
    kullanıldı, hangi görseller birbiriyle BİRLİKTE çıktı. generate_puzzle her başarılı bulmacadan sonra bunu günceller."""

    def __init__(self):
        self.counts = Counter()
        self.last = {}      # görsel -> en son kullanıldığı bulmacanın sıra numarası
        self.pairs = {}     # görsel -> onunla aynı bulmacada çıkmış diğer görseller
        self.n = 0          # şimdiye kadar üretilen bulmaca sayısı

    def update(self, image_words):
        ws = sorted(set(image_words))
        self.counts.update(ws)
        for a in ws:
            self.pairs.setdefault(a, set()).update(b for b in ws if b != a)
            self.last[a] = self.n
        self.n += 1

    def rested(self, rest):
        """Son 'rest' bulmacada kullanılmış (yani şimdi dinlenmesi gereken) görseller."""
        return {w for w, l in self.last.items() if self.n - l <= rest}


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
        if s.length < 2:
            continue  # tek harfli cevaplara görsel/bayrak konmaz
        if s.direction == 'across' and s.start_col == 1:
            eligible.append((s, (s.start_row, 0)))
        elif s.direction == 'down' and s.start_row == 1:
            eligible.append((s, (0, s.start_col)))
        elif s.direction == 'down' and s.start_row > 1 and s.start_col == 6:
            eligible.append((s, (s.start_row - 1, 6)))
        elif s.direction == 'across' and s.start_col > 1 and s.start_row == 8:
            eligible.append((s, (8, s.start_col - 1)))
    return eligible


def _slot_word(grid, slot):
    return ''.join(grid[c] for c in slot.cells())


def _find_anchor_slots(slots):
    """(row1'in 6 harfli slotu, col1'in 8 harfli slotu) çiftini bulur."""
    row1_slot = next(s for s in slots if s.direction == 'across' and s.start_row == 1 and s.start_col == 1)
    col1_slot = next(s for s in slots if s.direction == 'down' and s.start_row == 1 and s.start_col == 1)
    return row1_slot, col1_slot


def _pick_flag_seed(eligible, word_bank, rng, image_usage, banned=()):
    """Bayrak seçer: ÖNCE bayrak (az kullanılmış olanın şansı yüksek), SONRA o uzunlukta bir kenar hücresi.
    (Kısa bayraklar bulmacaya daha kolay sığar; bayrağı slottan önce seçmek ve kullanım sayısına göre
    ağırlıklandırmak FAS/İRAN/ÇİN gibi birkaç bayrağın hep çıkmasını önler.)"""
    lengths = {sl.length for sl, _ in eligible}
    words = [w for L in lengths for w in word_bank.flag_words_by_len.get(L, ()) if w not in banned]
    if not words:
        return None
    weights = [1.0 / (1 + image_usage.get(w, 0)) ** 2 for w in words]
    word = rng.choices(words, weights=weights)[0]
    sl, cell = rng.choice([(s, c) for s, c in eligible if s.length == len(word)])
    return sl, cell, word


def _pick_long_seed(eligible, anchors, word_bank, rng, image_usage, banned=()):
    """İskelet kutularından (6 harfli üst, 8 harfli sol) birine konacak UZUN görselli kelimeyi seçer.
    Önce kelime seçilir (az kullanılan önce), sonra o uzunluktaki iskelet kutusu."""
    by_len = {sl.length: sl for sl in anchors}
    cells = {sl.id: cell for sl, cell in eligible}
    words = [w for L in by_len for w in word_bank.image_words_by_len.get(L, ())
             if w not in banned and by_len[L].id in cells]
    if not words:
        return None
    weights = [1.0 / (1 + image_usage.get(w, 0)) ** 2 for w in words]
    word = rng.choices(words, weights=weights)[0]
    sl = by_len[len(word)]
    return sl, cells[sl.id], word


def _adjacent_map(eligible):
    """{slot.id: {kenar paylaşan (bitişik) ipucu hücresine sahip diğer slotların id'leri}}"""
    adj = {}
    for sl, (r, c) in eligible:
        adj[sl.id] = {o.id for o, (r2, c2) in eligible if o is not sl and abs(r - r2) + abs(c - c2) == 1}
    return adj


def generate_puzzle(word_bank, rng, max_tries_per_slot=60, max_backtracks=500, max_seconds=180,
                     anchor_registry_path=None, session_images=None):
    """Başarılı olursa (slots, all_breaks, grid, image_assignments) döner.
    image_assignments: {(row,col): {'type': 'image'|'flag', 'url': str}} -
    export_json.puzzle_to_json'a doğrudan verilir.

    Anchor çifti (row1'in 6 harflisi + col1'in 8 harflisi) daha önce üretilmiş HİÇBİR bulmacada
    kullanılmamış olacak şekilde garanti edilir - bkz. anchor_registry.py (kayıt, kelime bankasıyla aynı
    Excel dosyasının 'Uretilen_Bulmacalar' sayfasında tutulur). Başarılı her üretimden sonra bu ikili
    (ve bulmacadaki tüm kelimeler) kalıcı kayda otomatik eklenir; sonraki üretimlerde daha az kullanılmış
    kelimeler önce denenir.

    session_images: bir SessionMemory nesnesi (toplu üretimin hafızası). Verilirse: (1) bir görsel çıktıktan sonra
    sonraki REST_PUZZLES bulmacada çıkmaz (dinlenme), (2) aynı bulmacada birlikte çıkmış iki görsel bir daha
    birlikte çıkmaz (arkadaş yasağı); aynı görsel farklı arkadaşlarıyla tekrar kullanılabilir. Hedefe ulaşılamazsa
    sırayla bayrak şartı, uzun görsel şartı, dinlenme süresi (5 -> 2 -> 0), en son bu yasaklar ve görsel sayısı gevşetilir.

    max_seconds içinde üretilemezse None döner - çağıran taraf yeni bir rng ile tekrar dener."""
    anchor_path = anchor_registry_path or word_bank.xlsx_path
    used_anchors, word_usage, image_usage = load_registry(anchor_path)

    target = rng.randint(MIN_IMAGE_CELLS, MAX_IMAGE_CELLS)
    flag_required = rng.random() < FLAG_CHANCE and bool(word_bank.flag_words_by_len)
    long_wanted = (not flag_required) and rng.random() < LONG_IMAGE_CHANCE
    mem = session_images if hasattr(session_images, 'pairs') else None
    ban_active = mem is not None
    ban_level = 1                      # 1: tam dinlenme, 2: yarım, 3: dinlenme yok (arkadaş yasağı hep var), sonra yasaklar kalkar
    t_start = time.time()
    attempts = 0

    while time.time() - t_start < max_seconds:
        if attempts >= (FLAG_ATTEMPTS if (flag_required or long_wanted) else STAGE_ATTEMPTS) and (target > 0 or flag_required):
            # Hedefe ulaşılamadı: gevşet (önce bayrak şartı, sonra tekrar yasağı, en son görsel sayısı)
            if flag_required:
                flag_required = False
            elif long_wanted:
                long_wanted = False
            elif ban_active and ban_level < 3:
                ban_level += 1   # dinlenme süresi kısalır (5 -> 2 -> 0 bulmaca)
            elif ban_active:
                ban_active = False
            else:
                target -= 1
            attempts = 0

        slots, all_breaks, row_b, col_b = generate_dynamic_slots_v2(rng)
        row1_slot, col1_slot = _find_anchor_slots(slots)
        anchor_ids = {row1_slot.id, col1_slot.id}
        common = dict(max_tries_per_slot=max_tries_per_slot, anchor_slot_ids=(row1_slot.id, col1_slot.id),
                      used_anchor_pairs=used_anchors, word_usage=word_usage)

        eligible = [(sl, cell) for sl, cell in eligible_single_slots(slots)]   # iskelet (anchor) kutuları da görselli olabilir
        goal = None
        flag_assign = {}
        if target > 0:
            attempts += 1
            fill_slots, initial, initial_used = slots, None, None
            goal_target = target
            if flag_required or long_wanted:
                # Bayrağı (ya da iskelet kelimesi için UZUN bir görseli) ÖNCE yerleştir (ölçümde bayrağı aramaya
                # bırakmaktan çok daha hızlı), kalan görselleri ve kelimeleri onun etrafında ara.
                banned_now = mem.rested((REST_PUZZLES, 2, 0)[ban_level - 1]) if ban_active else ()
                seed_kind = 'flag' if flag_required else 'image'
                seed = (_pick_flag_seed(eligible, word_bank, rng, image_usage, banned_now) if flag_required
                        else _pick_long_seed(eligible, (row1_slot, col1_slot), word_bank, rng, image_usage, banned_now))
                if seed is None:
                    continue
                fslot, fcell, fword = seed
                flag_assign = {fcell: {'type': seed_kind,
                                       'url': word_bank.flag_clue(fword) if flag_required else word_bank.image_clue(fword)}}
                # bayrağın bitişiğindeki kutulara görsel konmaz
                eligible = [(sl, cell) for sl, cell in eligible if sl is not fslot
                            and not (NO_ADJACENT_IMAGES and abs(cell[0] - fcell[0]) + abs(cell[1] - fcell[1]) == 1)]
                fill_slots = [sl for sl in slots if sl is not fslot]
                initial = {c: fword[i] for i, c in enumerate(fslot.cells())}
                initial_used = {fword}
                goal_target = target - 1
            # Ön kontrol (çok ucuz): bu şablonda hedef kadar görsel alabilecek uzunlukta slot var mı?
            capable = [sl for sl, _ in eligible if word_bank.image_words_by_len.get(sl.length)]
            adj_map = _adjacent_map(eligible) if NO_ADJACENT_IMAGES else {}
            ub = max_independent_count({sl.id for sl in capable}, {k: frozenset(v) for k, v in adj_map.items()})
            if MAX_SHORT_IMAGES is not None:
                n_short = sum(1 for sl in capable if sl.length == 2)
                ub = min(ub, len(capable) - n_short + min(n_short, MAX_SHORT_IMAGES))
            if ub < goal_target:
                continue   # bu şablonda (bitişiklik ve kısa kelime kuralıyla) hedef kadar görsel sığmaz
            goal = {'eligible': {sl.id for sl, _ in eligible}, 'target': goal_target, 'flag_required': False,
                    'adjacent': adj_map, 'image_usage': image_usage, 'short_len': 2,
                    'banned': mem.rested((REST_PUZZLES, 2, 0)[ban_level - 1]) if ban_active else None,
                    'pair_ban': mem.pairs if ban_active else None,
                    'initial_images': [fword] if (flag_required or long_wanted) else []}
            if MAX_SHORT_IMAGES is not None:
                goal['max_short'] = MAX_SHORT_IMAGES
            grid = fill_grid(fill_slots, word_bank, max_backtracks=GOAL_BACKTRACKS, image_goal=goal,
                             initial_grid=initial, initial_used_words=initial_used, **common)
        else:
            grid = fill_grid(slots, word_bank, max_backtracks=max_backtracks, **common)
        if grid is None:
            continue
        if (_slot_word(grid, row1_slot), _slot_word(grid, col1_slot)) in used_anchors:
            continue   # (bayrak iskelet kelimesi olduysa) daha önce üretilmiş anchor çifti

        image_assignments = dict(flag_assign)
        for sl, cell in eligible:
            kind = goal['result'].get(sl.id) if goal else None
            if kind:
                word = _slot_word(grid, sl)
                url = word_bank.flag_clue(word) if kind == 'flag' else word_bank.image_clue(word)
                image_assignments[cell] = {'type': kind, 'url': url}

        all_words = [_slot_word(grid, sl) for sl in slots]
        image_words = [_slot_word(grid, sl) for sl, cell in eligible_single_slots(slots) if cell in image_assignments]
        save_used_anchor(_slot_word(grid, row1_slot), _slot_word(grid, col1_slot), anchor_path,
                         words=all_words, images=image_words)
        if mem is not None:
            mem.update(image_words)
        return slots, all_breaks, grid, image_assignments
    return None
