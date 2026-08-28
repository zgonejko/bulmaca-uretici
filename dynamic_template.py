"""9x7 şablonu: üst satır + sol sütun sabit ipucu, iç kısımdaki bölme
noktaları (kısa kelimelere ayıran ipucu hücreleri) HER ÜRETİMDE rastgele
ve dinamik olarak seçilir."""
import random
from slot_filler import Slot


def generate_dynamic_slots(rng):
    """8 satır x 6 sütunluk iç alan için dinamik bölme noktalarıyla slot listesi üretir.
    Dönüş: (slots, break_cells) - break_cells = iç kısımda ipucu hücresi olan (row,col) seti."""
    # Her sütun (1..6) için, o sütunun 8 satırlık dikey kelimesini nerede böleceğine karar ver.
    # break_row: None (bölme yok, tam 8 harflik kelime) veya 2..8 arası bir satır.
    break_row = {}
    for c in range(1, 7):
        # %70 ihtimalle böl (uzun 8 harfli kelime zor olduğu için genelde bölünsün),
        # %30 ihtimalle bölünmesin (çeşitlilik için bazen tam 8 harflik kelime dursun).
        if rng.random() < 0.7:
            break_row[c] = rng.randint(2, 8)
        else:
            break_row[c] = None

    break_cells = set()
    for c, br in break_row.items():
        if br is not None:
            break_cells.add((br, c))

    slots = []
    slot_id = 0

    # Dikey (down) slotlar
    for c in range(1, 7):
        br = break_row[c]
        if br is None:
            slots.append(Slot(f'D{slot_id}', 'down', 1, c, 8))
            slot_id += 1
        else:
            if br - 1 >= 2:  # üst parça (en az 2 harf olsun, çok kısa/anlamsız kelime olmasın)
                slots.append(Slot(f'D{slot_id}', 'down', 1, c, br - 1))
                slot_id += 1
            if 8 - br >= 2:  # alt parça
                slots.append(Slot(f'D{slot_id}', 'down', br + 1, c, 8 - br))
                slot_id += 1

    # Yatay (across) slotlar - o satırdaki bölme noktalarına göre bölünür.
    for r in range(1, 9):
        cuts = sorted(c for (br, c) in break_cells if br == r)
        segments = []
        prev = 1
        for cut in cuts:
            if cut > prev:
                segments.append((prev, cut - 1))
            prev = cut + 1
        if prev <= 6:
            segments.append((prev, 6))

        for (start_c, end_c) in segments:
            length = end_c - start_c + 1
            if length >= 2:  # çok kısa parçaları slot yapmıyoruz
                slots.append(Slot(f'A{slot_id}', 'across', r, start_c, length))
                slot_id += 1

    return slots, break_cells
