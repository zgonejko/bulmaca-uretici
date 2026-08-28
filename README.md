# Bulmaca Üretici

Çengel bulmaca oyunu için otomatik bulmaca üretim aracı. **Flutter uygulamasından
(`kelime-bulmaca`) tamamen bağımsızdır** — tek bağlantı noktası, ürettiği
JSON çıktısıdır (bkz. `export_json.py`).

## Mimari

```
Kelime Bankası (Excel: kelime + ipucu)
        │
        ▼
  word_bank.py  (yükleme, temizleme, uzunluk/pozisyon indeksleme)
        │
        ▼
dynamic_template_v2.py  (9x7 ızgara: üst satır + sol sütun sabit,
                          iç kısımda dinamik/rastgele çift-yönlü bölme noktaları)
        │
        ▼
  slot_filler.py  (genel amaçlı kısıt-tatmin / backtracking doldurma motoru)
        │
        ▼
  export_json.py  (Flutter'ın Puzzle modeliyle eşleşen JSON çıktısı)
        │
        ▼
     MySQL (bulmaca havuzu) ← PHP API ← Flutter uygulaması
```

## Dosyalar

- `word_bank.py` — Excel'den kelime+ipucu yükler, uzunluk ve pozisyon bazlı indeksler.
- `slot_filler.py` — Herhangi bir slot (kelime yeri) listesini, kelime bankasından
  gerçek kelimelerle dolduran genel amaçlı geri izlemeli (backtracking) çözücü.
- `dynamic_template_v2.py` — 9 satır x 7 sütunluk ızgara şablonu üretir; iç kısımdaki
  bölme/ipucu noktaları her üretimde rastgele ve **her zaman hem satırı hem sütunu
  aynı anda böler** (en alt satır/en sağ sütuna denk gelenler istisna, tek yönlü kalır).
- `export_json.py` — Üretilen bulmacayı uygulamanın okuyabileceği JSON formatına çevirir.
- `batch_test.py` — Toplu üretim testi (başarı oranı, hız ölçümü).

## Kullanım

```bash
pip install pandas openpyxl
python3 export_json.py   # örnek bir bulmaca üretip sample_puzzle.json'a yazar
python3 batch_test.py    # 30 bulmacalık toplu üretim testi çalıştırır
```

## Test sonuçları (son ölçüm)

- 30/30 başarı (%100), bulmaca başına ortalama ~0.5 saniye.
- Bulmaca başına 19-22 kelime, 4-8 dinamik bölme noktası.

## Durum / Sıradaki adımlar

- ~~Üst satır/sol sütun ipuçlarının nereden geleceği~~ → **çözüldü**: ayrı bir kaynağa
  gerek yok, her sütun/satırın ilk segmentinin çözülen kelimesinden otomatik türetiliyor.
- Nadir/az bilinen kelimeleri filtreleme — kullanıcı kendisi halledecek (kelime bankası tarafında).
- Zorluk skoru ataması (`ai_difficulty`) henüz yok — Bölüm 8'deki gibi gerçek kullanıcı
  verisiyle sonradan güncellenecek, üretim aşamasında boş bırakılıyor.
- PHP/MySQL'e gerçek kayıt (şu an sadece JSON dosyasına yazıyor).
