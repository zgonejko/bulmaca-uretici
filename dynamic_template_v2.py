"""9x7 şablon - v3: her satırda/sütunda kırılma sayısı artık RASTGELE (4-8)
DEĞİL, sabit bir kurala göre üretiliyor:

  - col2, col3, col4, col5, col6'nın HER BİRİ tam olarak 1 zorunlu kırılma alır.
    Bu zorunlu kırılmalar HİÇBİR ZAMAN en alt satırda (row8) olmaz - row2-7
    arasında rastgele bir satıra denk gelir.
  - Buna ek olarak tam 1 EKSTRA (6.) kırılma vardır ve bu HER ZAMAN row8'de,
    rastgele bir sütuna (col2-6 arası) yerleştirilir. Bu sütun böylece
    toplamda 2 kırılmalı olan TEK sütun olur (kural: bir bulmacada en fazla
    1 sütun 2 kırılma alabilir - bu mekanizma sayesinde otomatik sağlanıyor).
  - Toplam kırılma sayısı HER ZAMAN 6'dır.
  - Bir satırda en fazla 1 kırılma olabilir (iki kırılma asla aynı satırda
    olmaz) - zorunlu 5 kırılma farklı satırlara (row2-7 arasından 5 farklı
    satır) dağıtılır, ekstra 6. kırılma zaten ayrı bir satırdadır (row8).
  - Satırın en sağ hücresine (col6) denk gelen kırılmalar sadece AŞAĞI yönlü
    kalır, en alt satıra (row8) denk gelenler sadece SAĞA yönlü kalır - bu,
    segment sınırları sayesinde kendiliğinden doğru çıkıyor, ayrı bir kod
    gerekmiyor (bkz. _segment_lengths).

Tek harfli cevap YOKTUR: bir satır/sütunda tek harfe sığan parçalar kelime
sayılmaz (bkz. _build_slots). Bu yüzden her ipucu hücresinden en az bir kelime
başlamalı ve her harf hücresi en az bir kelimenin içinde olmalıdır
(bkz. _layout_ok) - bu iki koşulu sağlamayan şablonlar atılıp yenisi üretilir.
"""
from slot_filler import Slot
from word_bank import TEK_HARFLI_CEVAP


def _segment_lengths(breaks_sorted, total):
    segs = []
    prev = 1
    for b in breaks_sorted:
        if b > prev:
            segs.append((prev, b - 1))
        prev = b + 1
    if prev <= total:
        segs.append((prev, total))
    return segs


def _adjacent_conflict(all_breaks, r, c):
    # İki kırılma noktası bitişik olamaz (aralarında en az 1 harf hücresi
    # kalmalı), yoksa biri diğerinin ipucu vereceği hücreyi de bölme yapıp
    # boşa çıkarır.
    return (
        (r, c + 1) in all_breaks or (r, c - 1) in all_breaks or
        (r + 1, c) in all_breaks or (r - 1, c) in all_breaks
    )


def _segments_ok(row_breaks, col_breaks, r, c):
    # NOT: bir ucun (pozisyon 1 VEYA en son pozisyon) tek harflik bir segment
    # olması SORUN DEĞİL - o harf zaten kesişen bir başka cevaptan geliyor:
    # - pozisyon 1: col1'in 8 harfi / row1'in 6 harfi (sabit köşe cevaplar)
    # - en son pozisyon: o satırın kendi col6 hücresi (col6'nın KENDİ aşağı
    #   cevabından gelir) / o sütunun kendi row8 hücresi (row8'in KENDİ sağa
    #   cevabından gelir - double_col hariç, orada row8 zaten ayrı bir kırılma)
    # Sadece ortada kalan (her iki uca da değmeyen) 1 harflik bir segment
    # olursa bu geçersizdir - ama tek kırılmalı bir satır/sütunda böyle bir
    # segment zaten oluşamaz, bu kontrol yine de garanti altına alıyor.
    def ok(segs, total):
        return all(s == 1 or e == total or e - s + 1 >= 2 for s, e in segs)

    row_segs = _segment_lengths(sorted(row_breaks[r] | {c}), 6)
    col_segs = _segment_lengths(sorted(col_breaks[c] | {r}), 8)
    return ok(row_segs, 6) and ok(col_segs, 8)


def _try_generate(rng):
    """Tek bir deneme: başarılı olursa (row_breaks, col_breaks, all_breaks)
    döner, kısıtları sağlayamazsa None döner (çağıran taraf farklı bir
    sırayla tekrar dener)."""
    row_breaks = {r: set() for r in range(1, 9)}
    col_breaks = {c: set() for c in range(1, 7)}
    all_breaks = set()
    used_rows_for_primary = set()

    # 1) Her sütuna (col2-6) tam olarak 1 zorunlu kırılma - row8 HARİÇ.
    columns = [2, 3, 4, 5, 6]
    rng.shuffle(columns)
    for c in columns:
        candidate_rows = list(range(2, 8))  # row2..row7 (row8 bilinçli olarak dışarıda)
        rng.shuffle(candidate_rows)
        placed = False
        for r in candidate_rows:
            if r in used_rows_for_primary:
                continue
            if _adjacent_conflict(all_breaks, r, c):
                continue
            if not _segments_ok(row_breaks, col_breaks, r, c):
                continue
            row_breaks[r].add(c)
            col_breaks[c].add(r)
            all_breaks.add((r, c))
            used_rows_for_primary.add(r)
            placed = True
            break
        if not placed:
            return None

    # 2) Ekstra (6.) kırılma: HER ZAMAN row8'de, rastgele bir sütuna - ama
    # ASLA col6 (row8+col6 = "Y" köşesi, kurala göre hiçbir zaman soru olamaz).
    extra_columns = [2, 3, 4, 5]
    rng.shuffle(extra_columns)
    for c in extra_columns:
        r = 8
        if _adjacent_conflict(all_breaks, r, c):
            continue
        if not _segments_ok(row_breaks, col_breaks, r, c):
            continue
        row_breaks[r].add(c)
        col_breaks[c].add(r)
        all_breaks.add((r, c))
        return row_breaks, col_breaks, all_breaks

    return None


def _build_slots(row_breaks, col_breaks):
    """Kırılma noktalarından slot listesini üretir.
    TEK_HARFLI_CEVAP = True  : tek hücrelik parçalar da kendi (tek harfli) cevabı ve
                               ipucuyla slot olur - hiçbir harfin ipucusuz kalmaz.
    TEK_HARFLI_CEVAP = False : tek hücrelik parçalar kelime SAYILMAZ; o hücrenin harfi
                               kesişen diğer cevaptan gelir, ipucu hücresi boş kalır."""
    min_len = 1 if TEK_HARFLI_CEVAP else 2
    slots = []
    sid = 0
    for r in range(1, 9):
        for (s, e) in _segment_lengths(sorted(row_breaks[r]), 6):
            if e - s + 1 < min_len:
                continue
            slots.append(Slot(f'A{sid}', 'across', r, s, e - s + 1)); sid += 1
    for c in range(1, 7):
        for (s, e) in _segment_lengths(sorted(col_breaks[c]), 8):
            if e - s + 1 < min_len:
                continue
            slots.append(Slot(f'D{sid}', 'down', s, c, e - s + 1)); sid += 1
    return slots


def _layout_ok(slots, all_breaks):
    """Tek harfli slotlar atıldıktan sonra ızgara hâlâ tutarlı mı?
      1) Her ipucu (kırılma) hücresinden en az bir kelime başlamalı, yoksa
         boş/anlamsız bir ipucu hücresi kalır.
      2) Her harf hücresi en az bir kelimenin içinde olmalı, yoksa o harfin
         hiçbir cevabı olmaz.
    """
    starts = {(s.direction, s.start_row, s.start_col) for s in slots}
    for (r, c) in all_breaks:
        if ('across', r, c + 1) not in starts and ('down', r + 1, c) not in starts:
            return False
    covered = set()
    for s in slots:
        covered.update(s.cells())
    for r in range(1, 9):
        for c in range(1, 7):
            if (r, c) not in all_breaks and (r, c) not in covered:
                return False
    return True


def generate_dynamic_slots_v2(rng, max_attempts=500):
    slots = result = None
    for _ in range(max_attempts):
        result = _try_generate(rng)
        if result is None:
            continue
        row_breaks, col_breaks, all_breaks = result
        slots = _build_slots(row_breaks, col_breaks)
        if _layout_ok(slots, all_breaks):
            break
        result = None
    if result is None:
        raise RuntimeError(
            'Kırılma noktaları kurala uygun şekilde yerleştirilemedi '
            f'({max_attempts} denemede başarısız oldu) - bu normalde çok nadir '
            'olmalı, tekrar dene ya da ızgara/kural kısıtlarını gözden geçir.'
        )
    row_breaks, col_breaks, all_breaks = result
    return slots, all_breaks, row_breaks, col_breaks
