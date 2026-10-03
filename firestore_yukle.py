"""Uretilen bulmacalari Firebase (Firestore) 'puzzles' koleksiyonuna yukler.

Kullanim (bulmaca-uretici klasorunde):
    python firestore_yukle.py web/uretilen.json            -> yukler
    python firestore_yukle.py web/uretilen.json --deneme   -> hicbir sey yuklemez, sadece kontrol eder

Gerekenler:
    pip install google-auth requests
    servis-anahtari.json  (Firebase Console'dan indirilen anahtar, bu klasore konur)

Daha once yuklenmis bulmacalar (ayni id) atlanir, yani ayni dosyayi iki kez
calistirmak guvenlidir.
"""
import json
import os
import random
import sys
import warnings

warnings.filterwarnings('ignore')  # Python 3.8 eskidir uyarilarini gizle
from datetime import datetime, timezone

PROJECT_ID = 'kelimehane'
KOLEKSIYON = 'puzzles'
ANAHTAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'servis-anahtari.json')
BASE = 'https://firestore.googleapis.com/v1/projects/%s/databases/(default)/documents' % PROJECT_ID


def to_value(v):
    """Python degerini Firestore REST degerine cevirir."""
    if v is None:
        return {'nullValue': None}
    if isinstance(v, bool):
        return {'booleanValue': v}
    if isinstance(v, int):
        return {'integerValue': str(v)}
    if isinstance(v, float):
        return {'doubleValue': v}
    if isinstance(v, str):
        return {'stringValue': v}
    if isinstance(v, list):
        return {'arrayValue': {'values': [to_value(x) for x in v]}}
    if isinstance(v, dict):
        return {'mapValue': {'fields': {k: to_value(x) for k, x in v.items()}}}
    raise TypeError('Desteklenmeyen tur: %r' % type(v))


def dokuman_hazirla(p):
    """Bulmacayi Firestore dokumanina cevirir (uygulamanin okuyacagi alanlar)."""
    hucreler = p['cells']
    gorsel = 0
    bayrak = False
    for c in hucreler:
        urls = []
        if c.get('clue_image_url'):
            urls.append(c)
        for cl in c.get('clues') or []:
            if cl.get('image_url'):
                urls.append(cl)
        if urls:
            gorsel += 1
            if any(u.get('is_flag') for u in urls):
                bayrak = True
    veri = {
        'rows': p['rows'],
        'cols': p['cols'],
        'cells': hucreler,
        'letterFlow': p['letter_flow'],
        'wordCount': p.get('kelime_sayisi'),
        'imageCount': gorsel,
        'hasFlag': bayrak,
        'aiDifficulty': p.get('ai_difficulty'),
        'rand': random.random(),
        'createdAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    return {'fields': {k: to_value(v) for k, v in veri.items()}}


def hata(msg):
    print('HATA: ' + msg)
    sys.exit(1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    deneme = '--deneme' in sys.argv
    if not args:
        hata('Kullanim: python firestore_yukle.py web/uretilen.json')
    with open(args[0], encoding='utf-8') as f:
        veri = json.load(f)
    puzzles = veri['puzzles'] if isinstance(veri, dict) and 'puzzles' in veri else veri
    print('%d bulmaca bulundu.' % len(puzzles))

    if deneme:
        for p in puzzles:
            dokuman_hazirla(p)
        print('Deneme tamam: hepsi yuklemeye uygun. Hicbir sey yuklenmedi.')
        return

    if not os.path.exists(ANAHTAR):
        hata('servis-anahtari.json bulunamadi. Bu dosyayi %s klasorune koyun.' % os.path.dirname(ANAHTAR))
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except Exception as e:  # asil hatayi goster
        import traceback
        traceback.print_exc()
        hata('Paketler yuklenemedi. Asil hata: %r' % (e,))

    cred = service_account.Credentials.from_service_account_file(
        ANAHTAR, scopes=['https://www.googleapis.com/auth/datastore'])
    oturum = AuthorizedSession(cred)

    yuklenen = atlanan = basarisiz = 0
    for i, p in enumerate(puzzles, 1):
        pid = p['id']
        # currentDocument.exists=false: dokuman zaten varsa 409 doner, uzerine yazmaz.
        r = oturum.post(
            '%s/%s' % (BASE, KOLEKSIYON),
            params={'documentId': pid},
            json=dokuman_hazirla(p),
            timeout=60)
        if r.status_code == 200:
            yuklenen += 1
            print('%d/%d yuklendi' % (i, len(puzzles)))
        elif r.status_code == 409:
            atlanan += 1
            print('%d/%d zaten var, atlandi' % (i, len(puzzles)))
        else:
            basarisiz += 1
            print('%d/%d BASARISIZ (%s): %s' % (i, len(puzzles), r.status_code, r.text[:200]))
    print('Bitti. Yuklenen: %d, atlanan: %d, basarisiz: %d' % (yuklenen, atlanan, basarisiz))


if __name__ == '__main__':
    main()
