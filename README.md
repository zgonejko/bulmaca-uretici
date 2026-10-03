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
     Firestore (puzzles koleksiyonu) ← firestore_yukle.py ... Flutter uygulaması okur
```

## Dosyalar

- `word_bank.py` — Excel'den kelime+ipucu yükler, uzunluk ve pozisyon bazlı indeksler.
- `slot_filler.py` — Herhangi bir slot (kelime yeri) listesini, kelime bankasından
  gerçek kelimelerle dolduran genel amaçlı geri izlemeli (backtracking) çözücü.
- `dynamic_template_v2.py` — 9 satır x 7 sütunluk ızgara şablonu üretir; iç kısımdaki
  bölme/ipucu noktaları her üretimde rastgele ve **her zaman hem satırı hem sütunu
  aynı anda böler** (en alt satır/en sağ sütuna denk gelenler istisna, tek yönlü kalır).
- `export_json.py` — Üretilen bulmacayı uygulamanın okuyabileceği JSON formatına çevirir.
- `anchor_registry.py` — Üretilen her bulmacayı (anchor çifti + tüm kelimeler) `bulmaca.xlsx`
  içindeki **`Uretilen_Bulmacalar`** sayfasına kaydeder; aynı anchor çifti bir daha üretilmez,
  az kullanılmış kelimeler önce denenir.
- `puzzle_pipeline.py` — Tüm akışı birleştirir (şablon + doldurma + anchor kaydı + görsel/bayrak tercihi).
- `batch_test.py` — Toplu üretim testi: başarı oranı, hız ve kural kontrolleri.
- `generate_batch.py` — N bulmaca üretip JSON dosyasına yazar (web sayfası bunu çağırır).
- `firestore_yukle.py` — Üretilen JSON dosyasını Firebase a (Firestore puzzles) yükler; servis-anahtari.json gerekir (repoya EKLENMEZ).
- `web/` — Üretilen bulmacaları tarayıcıda **alt alta** gösteren sayfa (`index.php`, `viewer.js`,
  `style.css`, `config.php`). Bkz. aşağıdaki "Web görüntüleyici".

## Kurallar

- **Görsel ve bayrak:** Excel'de `tip` 1 = metin ipucu, 2 = görsel ipucu (cevap: kelime, soru: görsel adresi).
  Bayraklar da tip 2 olarak yazılır; adresi `/flags/` içeren görseller bayrak sayılır (eski tip 3 de çalışır).
  Her bulmacada 4-5 görsel olur; bunlardan biri ~%20 olasılıkla (4-6 bulmacadan birinde) bayraktır, en fazla 1 bayrak
  (`puzzle_pipeline.py` içinde `MIN_IMAGE_CELLS`, `MAX_IMAGE_CELLS`, `FLAG_CHANCE`). Hedef üretim sırasında garanti edilir;
  Hedef tutmazsa (süre değil DENEME sayısına göre) önce bayrak şartı, sonra görsel sayısı gevşetilir.
  Bayraklı bulmacalarda bayrak kelimesi önce yerleştirilir, kalan kelimeler onun etrafında aranır.
  Ek görsel kuralları: görselli kutular yan yana / alt alta olmaz; bir bulmacada en fazla 1 iki harfli görsel olur;
  aynı toplu üretimde (tek "Üret" tıklaması) bir görsel çıktıktan sonra sonraki 5 bulmacada çıkmaz (dinlenme) ve aynı
  bulmacada birlikte çıkmış iki görsel bir daha birlikte çıkmaz (arkadaş yasağı); aynı görsel farklı görsellerle tekrar
  kullanılabilir. "Kayda ekle" açıkken az kullanılmış görsel/bayraklar kalıcı olarak da öne alınır.
  İskelet kutuları (sol üstteki 8 harfli ve üstteki 6 harfli kelimenin ipucu kutuları) da görselli olabilir; bulmacaların
  ~%40'ında iskelet kelimesi baştan uzun (6 veya 8 harfli) bir görselle sabitlenir (`LONG_IMAGE_CHANCE`). Şablonda 7 harfli
  kenar kutusu olmadığı için 7 harfli görsel ve bayraklar hiç yerleşemez.
  Kurallar `puzzle_pipeline.py` başındaki `NO_ADJACENT_IMAGES` ve `MAX_SHORT_IMAGES` ile kapatılıp hızlandırılabilir.
  Görsel cevaplar küçük harfle yazılabilir. Görsel ipuçları yalnızca kenar (üst/sol) hücrelerine yerleşir.

- **Tek harfli cevaplar vardır.** Satır/sütunda tek hücre kalan yerler (her bulmacada 3-5 tane)
  kendi tek harfli cevabını ve ipucunu alır, böylece hiçbir harf ipucusuz kalmaz. Bunun için
  `bulmaca.xlsx` içinde tek harfli cevaplar (soru + cevap: `A`, `K`, `Y`...) bulunmalı. Bir
  bulmacada aynı tek harf iki kez kullanılmaz; ne kadar çok farklı harf eklenirse üretim o kadar
  hızlanır. (Kapatmak için `word_bank.py` içinde `TEK_HARFLI_CEVAP = False`; o zaman bu hücreler
  boş ipucuyla kalır.)
- **Aynı kökten kelimeler aynı bulmacada bulunmaz** (KÖY/KÖYLÜ, AKOR/AKORT, ACIMA/ACIMAK, DESTAN/DESTANSI...):
  biri diğerinin başıysa (en az 3 harf) ya da ilk 5 harfleri aynıysa çakışma sayılır.
- **Bir kez üretilen bulmaca tekrar üretilmez:** anchor çifti kalıcı kayıtta tutulur.
- Kelime bankası `bulmaca.xlsx` (bu klasörde). Excel'e yeni kelime/ipucu ekleyebilirsiniz; kayıt
  sayfasına dokunmayın. **Üretici çalışırken Excel dosyasını kapalı tutun.**

## Kullanım

Python 3.8 veya üstü gerekir (**Windows 7'de en son 3.8.10 çalışır**, 3.9+ kurulmaz).
Proje klasöründe (Windows'ta `python`, Mac/Linux'ta `python3`):

```bash
pip install pandas openpyxl
python export_json.py        # bir bulmaca üretir, sample_puzzle.json'a yazar ve kayda ekler
python batch_test.py 20      # 20 bulmacalık test (Excel'in geçici kopyasında çalışır, kaydı kirletmez)
```

## Web görüntüleyici (localhost + PHP)

Üretilen bulmacaları 9x7 şablonda, alt alta, cevapları göster/gizle seçeneğiyle gösterir.
Boyut `web/style.css` dosyasının en üstündeki `--o` değeriyle ayarlanır (0.7 = %30 küçük, 1 = ilk boyut).

1. Python bağımlılıklarını kurun (bir kez): `pip install pandas openpyxl`
   (Win7'de numpy/pandas sorun çıkarırsa: `pip install pandas==2.0.3 numpy==1.24.4 openpyxl`)
2. Proje klasöründe: `php -S localhost:8000 -t web` ve tarayıcıda `http://localhost:8000` açın.
   (XAMPP/WAMP kullanıyorsanız tüm klasörü `htdocs`/`www` altına koyup `.../bulmaca-uretici/web/` adresini açın.)
3. "Üret" düğmesi Python'u çalıştırır. `python` komutu bulunamazsa `web/config.php` içine
   `python.exe`'nin tam yolunu yazın. PHP'de `shell_exec` açık olmalı.
4. "Kayda ekle" işaretsizse önizlemedir (Excel'e dokunulmaz); işaretliyse bulmacalar kayda eklenir.

## Test sonuçları (son ölçüm)

- Tam alfabe tek harfli cevaplarla (~2100 kelime) bulmaca başına ortalama ~2 sn (geliştirme ortamında;
  eski bir bilgisayarda 2-3 kat daha yavaş olabilir). Farklı tek harfli cevap sayısı 20'nin altına
  düştükçe üretim yavaşlar, 8'in altında üretici hata verip durur. Kelime ekledikçe hızlanır.
- Bulmaca başına 22-26 kelime (3-5'i tek harfli), 6 bölme noktası.
- Görsel: 4-5 görsel her bulmacada garantili. Süre: ilk bulmacalar 1-5 sn, görsel havuzu tükendikçe (aynı toplu üretimde ~10+ bulmaca sonra) 10-30 sn'ye çıkabilir; eski bilgisayarda 2-3 kat daha uzun olabilir. Bankada özellikle kısa (2-5 harfli) görsel sayısı arttıkça hem hızlanır hem tekrar azalır.

## Durum / Sıradaki adımlar

- ~~Üst satır/sol sütun ipuçlarının nereden geleceği~~ → **çözüldü**: ayrı bir kaynağa
  gerek yok, her sütun/satırın ilk segmentinin çözülen kelimesinden otomatik türetiliyor.
- Nadir/az bilinen kelimeleri filtreleme — kullanıcı kendisi halledecek (kelime bankası tarafında).
- Zorluk skoru ataması (`ai_difficulty`) henüz yok — Bölüm 8'deki gibi gerçek kullanıcı
  verisiyle sonradan güncellenecek, üretim aşamasında boş bırakılıyor.
- PHP/MySQL'e gerçek kayıt (şu an sadece JSON dosyasına yazıyor).
