"""Toplu bulmaca üretir ve bir JSON dosyasına yazar. web/index.php bu betiği çağırır;
elle de çalıştırabilirsiniz.

Kullanım:
    python generate_batch.py ADET CIKTI.json            -> önizleme (kayda EKLENMEZ)
    python generate_batch.py ADET CIKTI.json --kayit    -> üretilenler Excel'deki kayda da eklenir
                                                           (aynı bulmaca bir daha üretilmez)

Not: Ekrana yalnızca ASCII yazılır (Windows konsol kod sayfası sorun çıkarmasın diye).
"""
import json
import os
import random
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime

from word_bank import WordBank, DEFAULT_XLSX, TEK_HARFLI_CEVAP
from puzzle_pipeline import generate_puzzle, SessionMemory
from export_json import puzzle_to_json

MAX_ADET = 30
MIN_TEK_HARF = 8   # bunun altinda tek harfli cevaplarla bulmaca uretmek (pratikte) mumkun degil


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    kayit = '--kayit' in sys.argv
    adet = max(1, min(MAX_ADET, int(args[0]))) if args else 5
    cikti = args[1] if len(args) > 1 else 'uretilen.json'

    tmp_dir = None
    xlsx = DEFAULT_XLSX
    if not kayit:
        # Önizleme: Excel'in geçici kopyasında çalış, asıl dosyaya HİÇ yazma.
        tmp_dir = tempfile.mkdtemp()
        xlsx = os.path.join(tmp_dir, 'kopya.xlsx')
        shutil.copy(DEFAULT_XLSX, xlsx)

    try:
        wb = WordBank(xlsx)
        if TEK_HARFLI_CEVAP:
            n_tek = len(wb.words_by_len.get(1, []))
            if n_tek < MIN_TEK_HARF:
                print('HATA: bulmaca.xlsx icinde yalnizca %d farkli tek harfli cevap var. Her bulmacada 3-5 tek harfli '
                      'cevap gerekir, hepsi birbirinden farkli olmali. En az %d, tercihen 20+ farkli tek harf '
                      'ekleyin (soru | cevap | tip = 1, cevap tek buyuk harf).' % (n_tek, MIN_TEK_HARF))
                sys.exit(3)
            if n_tek < 20:
                print('NOT: %d farkli tek harfli cevap var; uretim yavas olabilir (20+ onerilir).' % n_tek)
        puzzles = []
        basarisiz = 0
        kullanilan_gorseller = SessionMemory()   # bu toplu üretimde kullanılan görseller/bayraklar: tekrar kullanılmaz
        t0 = time.time()
        for i in range(adet):
            result = None
            for _ in range(2):
                result = generate_puzzle(wb, random.Random(), session_images=kullanilan_gorseller)
                if result:
                    break
            if not result:
                basarisiz += 1
                print('Bulmaca %d: uretilemedi' % (i + 1))
                continue
            slots, breaks, grid, image_assignments = result
            p = puzzle_to_json(grid, slots, breaks, wb, image_assignments=image_assignments)
            p['kelime_sayisi'] = len(slots)
            puzzles.append(p)
            print('Bulmaca %d: tamam' % (i + 1))
            sys.stdout.flush()

        veri = {
            'olusturma': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sure_sn': round(time.time() - t0, 1),
            'kayit': kayit,
            'istenen': adet,
            'basarisiz': basarisiz,
            'puzzles': puzzles,
        }
        with open(cikti, 'w', encoding='utf-8') as f:
            json.dump(veri, f, ensure_ascii=True)  # ASCII-güvenli: PHP json_decode sorunsuz okur
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as e:  # örn. Excel açık olduğu için kayıt yazılamadı
        print('HATA: %s' % e)
        sys.exit(2)
