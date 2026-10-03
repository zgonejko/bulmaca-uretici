"""Genel amaçlı slot tabanlı çengel bulmaca doldurma motoru.
Herhangi bir ızgara şablonunu (slot listesini) gerçek kelime bankasından
kelimelerle doldurur - kesişen kısıtları (ortak hücreler) çözerek."""
import random
import math
from collections import Counter


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


# --- Benzer kelime kuralı ---------------------------------------------------
# Aynı bulmacada aynı kökten türemiş kelimeler birlikte bulunmasın:
#   KÖY / KÖYLÜ, AKOR / AKORT, ACIMA / ACIMAK, DESTAN / DESTANSI, AKLANMA / AKLANMAK ...
# Kural: iki kelimeden
#   (a) kısa olan (en az 3 harfli), uzun olanın BAŞI ise (kelime diğerinin
#       başı olarak geçiyorsa), YA DA
#   (b) ikisinin ilk 5 harfi aynı ise
# çakışma sayılır. ARABA / ARMUT veya KALEM / KALEP gibi sadece birkaç harfi
# tesadüfen aynı olan kelimeler çakışma SAYILMAZ.
MIN_ROOT = 3
LONG_PREFIX = 5


def _prefix_conflict(word, used_words):
    """Kuralın yavaş ama açık hali - referans olarak ve testlerde kullanılır.
    (fill_grid içinde aynı kuralın hızlı hali, _ConflictIndex, kullanılır.)"""
    for u in used_words:
        a, b = (word, u) if len(word) <= len(u) else (u, word)  # a = kısa olan
        p = 0
        while p < len(a) and a[p] == b[p]:
            p += 1
        if p >= LONG_PREFIX or (p == len(a) and len(a) >= MIN_ROOT):
            return True
    return False


class _StaticConflicts:
    """Kelime bankası için BİR KEZ hesaplanan çakışma bilgisi (word_bank üzerinde önbelleklenir).
    conflicts_of(u): u yerleştirilirse yasaklanan tüm banka kelimeleri (u'nun kendisi dahil)."""

    def __init__(self, word_bank):
        all_words = set()
        for pool in (word_bank.words_by_len, word_bank.flag_words_by_len, word_bank.image_words_by_len):
            for words in pool.values():
                all_words.update(words)
        self.all_words = all_words
        self.by_prefix = {}   # öz-önek (>=MIN_ROOT harf) -> o önekle başlayan daha uzun kelimeler
        self.by_first5 = {}   # ilk 5 harf -> >=5 harfli kelimeler
        for w in all_words:
            for k in range(MIN_ROOT, len(w)):
                self.by_prefix.setdefault(w[:k], []).append(w)
            if len(w) >= LONG_PREFIX:
                self.by_first5.setdefault(w[:LONG_PREFIX], []).append(w)
        self._cache = {}

    def conflicts_of(self, u):
        res = self._cache.get(u)
        if res is None:
            c = {u}
            c.update(self.by_prefix.get(u, ()))                      # u, bunların başı
            if len(u) >= LONG_PREFIX:
                c.update(self.by_first5.get(u[:LONG_PREFIX], ()))    # ilk 5 harf aynı
            for k in range(MIN_ROOT, len(u)):                        # bunlar u'nun başı
                if u[:k] in self.all_words:
                    c.add(u[:k])
            res = tuple(c)
            self._cache[u] = res
        return res


class _ConflictIndex:
    """_prefix_conflict kuralının hızlı hali: yerleştirilen kelimelerin yasakladığı kelimeleri
    sayaçla tutar (geri izlemede güvenle geri alınır). `w in blocked` ise w yasaktır."""

    def __init__(self, word_bank):
        static = getattr(word_bank, '_static_conflicts', None)
        if static is None:
            static = _StaticConflicts(word_bank)
            word_bank._static_conflicts = static
        self.static = static
        self.count = {}
        self.blocked = set()   # yasaklı kelimeler (küme: aday kümelerinden C hızında çıkarılır)

    def add(self, w):
        c = self.count
        for x in self.static.conflicts_of(w):
            n = c.get(x, 0) + 1
            c[x] = n
            if n == 1:
                self.blocked.add(x)

    def remove(self, w):
        c = self.count
        for x in self.static.conflicts_of(w):
            n = c[x] - 1
            c[x] = n
            if n == 0:
                self.blocked.discard(x)


def max_independent_count(ids, adjacent, _cache=None):
    """'ids' içinden, birbirine BİTİŞİK olmayan en fazla kaç slot seçilebilir (en büyük bağımsız küme).
    Kenar hücreleri zincir gibi dizildiği için küçük ve hızlıdır. Görsel hedefine ulaşılıp ulaşılamayacağını
    erkenden anlamak için kullanılır."""
    cache = _cache if _cache is not None else {}
    ids = frozenset(ids)
    if ids in cache:
        return cache[ids]
    best = 0
    if ids:
        v = max(ids, key=lambda x: len(adjacent.get(x, ()) & ids))
        nb = adjacent.get(v, frozenset()) & ids
        if not nb:
            best = len(ids)   # hiç bitişik yok: hepsi seçilebilir
        else:
            best = max(max_independent_count(ids - {v}, adjacent, cache),
                       1 + max_independent_count(ids - nb - {v}, adjacent, cache))
    cache[ids] = best
    return best




# =====================================================================================================
#  BİT MASKESİ TABANLI ÇÖZÜCÜ
#
#  Her kelimeye bir bit numarası verilir; "şu uzunlukta, şu konumda, şu harfi içeren kelimeler" gibi
#  tüm kümeler büyük birer TAM SAYI (bit maskesi) olarak saklanır. Küme kesişimi (&), birleşimi (|)
#  ve çıkarma (& ~) tek bir makine işlemidir; önceki sürümde bunlar yüzlerce kelimelik Python
#  döngüleriydi. Çözücü her adımda tüm slotların aday kümesini bu maskelerle günceller ve komşu slotlar
#  arası uyumu (arc consistency) tam yayar - ama artık çok ucuza.
# =====================================================================================================

def _get_static(word_bank):
    static = getattr(word_bank, '_static_conflicts', None)
    if static is None:
        static = _StaticConflicts(word_bank)
        word_bank._static_conflicts = static
    return static


class _BitIndex:
    """Kelime bankası için BİR KEZ kurulan bit maskeleri (word_bank üzerinde önbelleklenir)."""

    def __init__(self, word_bank):
        text, image, flag = set(), set(), set()
        for ws in word_bank.words_by_len.values():
            text.update(ws)
        for ws in word_bank.image_words_by_len.values():
            image.update(ws)
        for ws in word_bank.flag_words_by_len.values():
            flag.update(ws)
        self.words = sorted(text | image | flag)
        self.index = {w: i for i, w in enumerate(self.words)}

        len_bits, lp_bits = {}, {}
        for i, w in enumerate(self.words):
            L = len(w)
            len_bits.setdefault(L, []).append(i)
            for pos, ch in enumerate(w):
                lp_bits.setdefault((L, pos), {}).setdefault(ch, []).append(i)

        def to_mask(idxs):
            m = 0
            for i in idxs:
                m |= 1 << i
            return m

        self.lenmask = {L: to_mask(v) for L, v in len_bits.items()}
        self.lp = {key: {ch: to_mask(v) for ch, v in d.items()} for key, d in lp_bits.items()}
        self.NORMAL = to_mask(self.index[w] for w in text)
        self.IMAGE = to_mask(self.index[w] for w in image)
        self.FLAG = to_mask(self.index[w] for w in flag)
        self.static = _get_static(word_bank)
        self._conf = {}
        self.am_cache = {}   # (komşu uzunluğu, konum, harfler) -> izinli kelimeler maskesi

    def conf_mask(self, i):
        """i numaralı kelime yerleştirilirse yasaklanan tüm kelimeler (kendisi dahil) - maske olarak."""
        m = self._conf.get(i)
        if m is None:
            m = 0
            for x in self.static.conflicts_of(self.words[i]):
                j = self.index.get(x)
                if j is not None:
                    m |= 1 << j
            self._conf[i] = m
        return m


def _bits(m):
    """Maskedeki set edilmiş bit numaraları."""
    return [i for i, ch in enumerate(bin(m)[:1:-1]) if ch == '1']


def _popcount(m):
    return bin(m).count('1')


def fill_grid(slots, word_bank, max_tries_per_slot=40, max_backtracks=20000,
              initial_grid=None, initial_used_words=None,
              anchor_slot_ids=None, used_anchor_pairs=None, word_usage=None, image_goal=None):
    """Geri izlemeli arama (backtracking) ile ızgarayı doldurur.

    Her slotun aday kümesi bir bit maskesidir. Bir kelime yerleştirilince (1) o kelimeyle çakışan
    (aynı/benzer) kelimeler tüm slotlardan çıkarılır, (2) kesişen komşu slotların adayları, ortak
    hücredeki harfi destekleyenlerle sınırlanır ve bu sınırlama komşulara yayılır (arc consistency).
    Bir slotun adayı tükenirse o yol hemen bırakılır; hâlâ seçenek olan yollarda en az adaylı slot
    önce doldurulur.

    initial_grid / initial_used_words: önceden yerleştirilmiş harfler ve kelimeler (örn. bayrak) -
    'slots' listesine önceden yerleştirilen slotu DAHIL ETMEYİN.

    anchor_slot_ids=(row1_id, col1_id), used_anchor_pairs={(kelime1, kelime2), ...}: daha önce üretilmiş
    anchor çiftleri tekrar oluşmaz.

    word_usage: {kelime: şimdiye kadar kaç bulmacada kullanıldı}; eşit durumdaki adaylar arasında daha
    az kullanılan önce denenir (yasak değil, sadece sıra).

    image_goal: görsel/bayrak HEDEFİ - arama sırasında GARANTİ edilir:
        'eligible': {slot.id, ...}   görsel konabilecek kenar slotları
        'target': 5                  tam bu kadar slot görselli (bayrak dahil) kelimeyle dolsun
        'flag_required': False       True: tam 1 tanesi bayrak olsun; False: hiç bayrak olmasın
        'adjacent': {id: {id,...}}   BİTİŞİK ipucu hücreleri aynı anda görselli olmaz
        'image_usage': {kelime: n}   az kullanılmış görsel/bayrak önce denenir
        'max_short', 'short_len'     bu uzunluktaki görselli kelime en fazla bu kadar
        'banned': {kelime, ...}      bu görsel/bayraklar HİÇ kullanılmaz
        'pair_ban': {kelime: {kelime,...}}  daha önce birlikte çıkmış görseller aynı bulmacada birlikte olmaz
        'initial_images': [kelime,...]      önceden yerleştirilmiş görsel/bayrak kelimeleri (arkadaş yasağı için)
    Başarıda image_goal['result'] = {slot.id: 'image'|'flag'} olarak doldurulur.

    Dönüş: {(row,col): harf} sözlüğü veya None. Deneme sayısı fill_grid.last_nodes içindedir."""
    bi = getattr(word_bank, '_bit_index', None)
    if bi is None:
        bi = word_bank._bit_index = _BitIndex(word_bank)
    words, lp = bi.words, bi.lp

    grid0 = dict(initial_grid) if initial_grid else {}
    used_anchor_pairs = used_anchor_pairs or set()
    word_usage = word_usage or {}
    anchor_a, anchor_b = anchor_slot_ids if anchor_slot_ids else (None, None)

    goal = image_goal
    eligible_ids = set(goal['eligible']) if goal else set()
    target = goal['target'] if goal else 0
    flag_required = bool(goal and goal.get('flag_required'))
    adjacent = {k: frozenset(v) for k, v in (goal.get('adjacent') or {}).items()} if goal else {}
    image_usage = (goal.get('image_usage') or {}) if goal else {}
    max_short = goal.get('max_short') if goal else None
    short_len = goal.get('short_len', 2) if goal else 2
    banned_mask = 0
    for w in ((goal.get('banned') or ()) if goal else ()):
        j = bi.index.get(w)
        if j is not None:
            banned_mask |= 1 << j

    pair_ban = (goal.get('pair_ban') or {}) if goal else {}
    pm_cache = {}

    def pmask(wi):
        """wi numaralı görselin 'arkadaş yasağı' maskesi: onunla birlikte olmaması gereken kelimeler."""
        m = pm_cache.get(wi)
        if m is None:
            m = 0
            for x in pair_ban.get(words[wi], ()):
                j = bi.index.get(x)
                if j is not None:
                    m |= 1 << j
            pm_cache[wi] = m
        return m

    ibm0 = 0
    for w in ((goal.get('initial_images') or ()) if goal else ()):
        j = bi.index.get(w)
        if j is not None:
            ibm0 |= pmask(j)

    NORM = bi.NORMAL
    IMGOK = bi.IMAGE & ~banned_mask          # görsel olarak kullanılabilecek kelimeler
    FLGOK = bi.FLAG & ~banned_mask           # bayrak olarak kullanılabilecek kelimeler
    IMGX = IMGOK & ~NORM                     # SADECE görsel olarak var olan kelimeler (metin ipucu yok)
    FLGX = FLGOK & ~NORM

    # --- slot tabloları ---
    sid_all = [s.id for s in slots]
    length = {s.id: s.length for s in slots}
    cells_of = {s.id: s.cells() for s in slots}
    cell_slots = {}
    for sid in sid_all:
        for pos, c in enumerate(cells_of[sid]):
            cell_slots.setdefault(c, []).append((sid, pos))
    cross = {sid: [] for sid in sid_all}     # sid -> [(komşu id, bu slottaki konum, komşudaki konum)]
    for lst in cell_slots.values():
        for (a, pa) in lst:
            for (b, pb) in lst:
                if a != b:
                    cross[a].append((b, pa, pb))
    adj_sets = adjacent
    mis_cache = {}

    # --- başlangıç yasakları ---
    blocked0 = 0
    for w in (initial_used_words or ()):
        j = bi.index.get(w)
        if j is not None:
            blocked0 |= bi.conf_mask(j)

    # --- başlangıç aday kümeleri ---
    img_ok0 = frozenset(sid for sid in sid_all if sid in eligible_ids) if target > 0 else frozenset()
    flag_ok0 = img_ok0 if flag_required else frozenset()
    dom0 = {}
    for sid in sid_all:
        L = length[sid]
        base = NORM
        if sid in img_ok0:
            base |= IMGX
        if sid in flag_ok0:
            base |= FLGX
        base &= bi.lenmask.get(L, 0)
        for pos, c in enumerate(cells_of[sid]):
            if c in grid0:
                base &= lp.get((L, pos), {}).get(grid0[c], 0)
        base &= ~blocked0
        base &= ~(ibm0 & (IMGX | FLGX))
        dom0[sid] = base

    def propagate(dom, queue):
        """Komşu uyumu yayılımı: slotun aday kelimelerinin her konumda desteklediği harflere göre komşuların
        adayları süzülür; değişen komşular kuyruğa girer. Bir slotun adayı tükenirse False."""
        queue = list(queue)
        inq = set(queue)
        while queue:
            sid = queue.pop()
            inq.discard(sid)
            d = dom[sid]
            L = length[sid]
            present = {}
            for (t, ps, pt) in cross[sid]:
                pr = present.get(ps)
                if pr is None:
                    pr = present[ps] = tuple(ch for ch, m in lp[(L, ps)].items() if d & m)
                Lt = length[t]
                lpt = lp[(Lt, pt)]
                key = (Lt, pt, pr)
                am = bi.am_cache.get(key)
                if am is None:
                    am = 0
                    for ch in pr:
                        am |= lpt.get(ch, 0)
                    if len(bi.am_cache) > 200000:
                        bi.am_cache.clear()
                    bi.am_cache[key] = am
                old = dom[t]
                new = old & am
                if new != old:
                    if not new:
                        return False
                    dom[t] = new
                    if t not in inq:
                        queue.append(t)
                        inq.add(t)
        return True

    counter = [0]
    result = {}

    def solve(dom, todo, assigned, img_assigned, img_ok, flag_ok, short_used, ibm):
        if counter[0] > max_backtracks:
            return False
        n_img = len(img_assigned)
        if not todo:
            if goal and (n_img != target or (flag_required and 'flag' not in img_assigned.values())):
                return False
            result['assigned'] = assigned
            result['img'] = img_assigned
            return True

        if goal:
            need_img = n_img < target
            need_flag = flag_required and 'flag' not in img_assigned.values()
            if need_flag and not need_img:
                return False
            if need_img:
                cap, flag_cap = [], []
                for sid in todo:
                    if sid not in eligible_ids:
                        continue
                    d = dom[sid]
                    a_img = sid in img_ok and (d & IMGOK & ~ibm)
                    a_flag = sid in flag_ok and (d & FLGOK & ~ibm)
                    if a_img or a_flag:
                        cap.append(sid)
                    if a_flag:
                        flag_cap.append(sid)
                if need_flag and not flag_cap:
                    return False
                ub = max_independent_count(cap, adj_sets, mis_cache) if adj_sets else len(cap)
                if max_short is not None:
                    n_sh = sum(1 for sid in cap if length[sid] == short_len)
                    ub = min(ub, len(cap) - n_sh + min(n_sh, max(max_short - short_used, 0)))
                if n_img + ub < target:
                    return False
                changed = []
                if n_img + len(cap) == target:       # sınırdayız: kalan görsel-aday slotlar görsele ZORLANIR
                    for sid in cap:
                        keep = (IMGOK & ~ibm if sid in img_ok else 0) | (FLGOK & ~ibm if sid in flag_ok else 0)
                        nv = dom[sid] & keep
                        if nv != dom[sid]:
                            dom[sid] = nv
                            changed.append(sid)
                if need_flag and len(flag_cap) == 1:   # bayrak konabilecek tek slot kaldı: ZORUNLU bayrak
                    sid = flag_cap[0]
                    nv = dom[sid] & FLGOK & ~ibm
                    if nv != dom[sid]:
                        dom[sid] = nv
                        changed.append(sid)
                if changed and not propagate(dom, changed):
                    return False

        # En az adaylı slotu seç
        best, best_key = None, None
        for sid in todo:
            d = dom[sid]
            if not d:
                return False
            key = (_popcount(d), -length[sid])
            if best_key is None or key < best_key:
                best, best_key = sid, key
        sid = best
        d = dom[sid]
        can_flag = sid in flag_ok
        can_img = sid in img_ok

        fl_m = (d & FLGOK & ~ibm) if can_flag else 0
        im_m = (d & IMGOK & ~ibm & ~fl_m) if can_img else 0
        rest_m = d & ~fl_m & ~im_m
        groups = []
        for m, kind, usage in ((fl_m, 'flag', image_usage), (im_m, 'image', image_usage), (rest_m, None, word_usage)):
            if m:
                lst = _bits(m)
                random.shuffle(lst)
                if usage:
                    lst.sort(key=lambda i: usage.get(words[i], 0))
                groups.append((lst, kind))
        todo2 = [x for x in todo if x != sid]

        tried = 0
        for lst, kind in groups:
            for wi in lst:
                if tried >= max_tries_per_slot:
                    return False
                if used_anchor_pairs and sid in (anchor_a, anchor_b):
                    other = anchor_b if sid == anchor_a else anchor_a
                    ow = assigned.get(other)
                    if ow is not None:
                        pair = (words[wi], words[ow]) if sid == anchor_a else (words[ow], words[wi])
                        if pair in used_anchor_pairs:
                            continue
                tried += 1
                counter[0] += 1
                if counter[0] > max_backtracks:
                    return False

                conf = bi.conf_mask(wi)
                nd = dict(dom)
                nd[sid] = 1 << wi
                changed = [sid]
                ok = True
                for t in todo2:
                    x = nd[t]
                    y = x & ~conf
                    if y != x:
                        if not y:
                            ok = False
                            break
                        nd[t] = y
                        changed.append(t)
                if not ok:
                    continue

                img2, flag2, short2 = img_ok - {sid}, flag_ok - {sid}, short_used
                ibm2 = ibm | (pmask(wi) if kind else 0)
                if ibm2 != ibm:   # yeni arkadaş yasakları: yalnız-görsel kelimeleri komşu slotların adaylarından çıkar
                    drop = ibm2 & (IMGX | FLGX)
                    for t in todo2:
                        nv = nd[t] & ~drop
                        if nv != nd[t]:
                            if not nv:
                                ok = False
                                break
                            nd[t] = nv
                            changed.append(t)
                    if not ok:
                        continue
                imga2 = img_assigned
                if kind:
                    imga2 = dict(img_assigned)
                    imga2[sid] = kind
                    lose = adjacent.get(sid, frozenset())
                    img2 = img2 - lose
                    flag2 = flag2 - lose
                    if kind == 'image' and length[sid] == short_len:
                        short2 += 1
                    if len(imga2) >= target:
                        img2, flag2 = frozenset(), frozenset()
                    if max_short is not None and short2 >= max_short:
                        img2 = frozenset(x for x in img2 if length[x] != short_len)
                    if kind == 'flag':
                        flag2 = frozenset()
                # İzni kalmayan slotlardan yalnız-görsel/yalnız-bayrak kelimeleri çıkar
                for t in todo2:
                    if t in img_ok and t not in img2:
                        nv = nd[t] & ~IMGX
                        if nv != nd[t]:
                            if not nv:
                                ok = False
                                break
                            nd[t] = nv
                            changed.append(t)
                    if t in flag_ok and t not in flag2:
                        nv = nd[t] & ~FLGX
                        if nv != nd[t]:
                            if not nv:
                                ok = False
                                break
                            nd[t] = nv
                            changed.append(t)
                if not ok or not propagate(nd, changed):
                    continue
                assigned2 = dict(assigned)
                assigned2[sid] = wi
                if solve(nd, todo2, assigned2, imga2, img2, flag2, short2, ibm2):
                    return True
        return False

    success = False
    d0 = dict(dom0)
    if all(d0[s] for s in sid_all) and propagate(d0, sid_all):
        success = solve(d0, list(sid_all), {}, {}, img_ok0, flag_ok0, 0, ibm0)
    fill_grid.last_nodes = counter[0]
    if not success:
        return None
    grid = dict(grid0)
    by_id = {s.id: s for s in slots}
    for sid, wi in result['assigned'].items():
        w = words[wi]
        by_id[sid].solved_word = w
        for pos, c in enumerate(cells_of[sid]):
            grid[c] = w[pos]
    if goal is not None:
        goal['result'] = dict(result['img'])
    return grid
