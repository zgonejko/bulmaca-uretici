<?php
// Bulmaca görüntüleyici: Python üreticiyi çalıştırır, sonucu alt alta gösterir.
// Kullanım: proje klasöründe  php -S localhost:8000 -t web   ya da klasörü htdocs/www altına koyun.
require __DIR__ . '/config.php';

$root    = dirname(__DIR__);                 // generate_batch.py'nin olduğu klasör
$outFile = __DIR__ . DIRECTORY_SEPARATOR . 'uretilen.json';
$hata    = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    @set_time_limit(0);                      // üretim birkaç dakika sürebilir
    $adet  = isset($_POST['adet']) ? (int)$_POST['adet'] : 5;
    $adet  = max(1, min(30, $adet));
    $kayit = !empty($_POST['kayit']);

    if (!function_exists('shell_exec')) {
        $hata = "PHP'de shell_exec kapalı (php.ini -> disable_functions). Açıp tekrar deneyin.";
    } else {
        if (file_exists($outFile)) { @unlink($outFile); }
        chdir($root);
        $cmd = escapeshellarg($PYTHON) . ' generate_batch.py ' . $adet . ' ' .
               escapeshellarg($outFile) . ($kayit ? ' --kayit' : '') . ' 2>&1';
        $cikti = shell_exec($cmd);
        if (function_exists('iconv')) {   // Windows (Türkçe) hata mesajlarını okunur hale getir
            $c = @iconv('CP857', 'UTF-8//IGNORE', (string)$cikti);
            if ($c !== false) { $cikti = $c; }
        }
        if (!file_exists($outFile)) {
            $hata = "Üretim başarısız oldu. Python'un çıktısı:\n\n" . trim((string)$cikti) .
                    "\n\nÇalıştırılan komut:\n" . $cmd;
        }
    }
}

$veri = null;
if (file_exists($outFile)) {
    $veri = json_decode(file_get_contents($outFile), true);
}
?><!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>Bulmaca Üretici - Görüntüleyici</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<h1>Bulmaca Üretici</h1>

<form method="post" class="ust-panel">
  <label>Kaç bulmaca: <input type="number" name="adet" value="<?php echo isset($_POST['adet']) ? (int)$_POST['adet'] : 5; ?>" min="1" max="30"></label>
  <label><input type="checkbox" name="kayit" value="1" <?php echo !empty($_POST['kayit']) ? 'checked' : ''; ?>> Kayda ekle (bir daha üretilmesin)</label>
  <button type="submit">Üret</button>
  <label style="margin-left:18px"><input type="checkbox" id="cevapGoster" checked> Cevapları göster</label>
  <div class="bilgi">Her bulmaca yaklaşık 1-30 saniye sürer (görsel kuralları yüzünden; ilk bulmacalar hızlı, sonrakiler yavaşlar); sayfa üretim bitene kadar bekler. "Kayda ekle" işaretliyse <b>bulmaca.xlsx</b> dosyasına yazılır, o yüzden Excel'de açık olmamalı.</div>
</form>

<?php if ($hata !== '') { ?>
  <div class="hata"><?php echo htmlspecialchars($hata); ?></div>
<?php } ?>

<?php if ($veri && !empty($veri['puzzles'])) { ?>
  <div class="bilgi" style="margin-bottom:14px">
    <?php echo count($veri['puzzles']); ?> bulmaca &middot; <?php echo htmlspecialchars($veri['olusturma']); ?> &middot;
    <?php echo htmlspecialchars((string)$veri['sure_sn']); ?> sn &middot;
    <?php echo $veri['kayit'] ? 'kayda eklendi' : 'önizleme (kayda eklenmedi)'; ?>
    <?php if (!empty($veri['basarisiz'])) { echo ' &middot; üretilemeyen: ' . (int)$veri['basarisiz']; } ?>
  </div>
  <div id="liste"></div>
  <script src="viewer.js"></script>
  <script>
    var VERI = <?php echo json_encode($veri['puzzles'], JSON_HEX_TAG | JSON_HEX_AMP); ?>;
    var html = '';
    for (var i = 0; i < VERI.length; i++) { html += renderPuzzle(VERI[i], i + 1); }
    document.getElementById('liste').innerHTML = html;
    var kutu = document.getElementById('cevapGoster');
    function uygula() {
      var l = document.getElementById('liste');
      l.className = kutu.checked ? '' : 'gizle-cevap';
    }
    kutu.onclick = uygula;
    uygula();
  </script>
<?php } elseif ($hata === '') { ?>
  <div class="bilgi">Henüz bulmaca yok - "Üret" düğmesine basın.</div>
<?php } ?>
</body>
</html>
