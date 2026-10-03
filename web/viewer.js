/* Bulmaca görüntüleyici - saf JavaScript, kütüphane gerektirmez.
   renderPuzzle(p, no) bir bulmacanın HTML'ini (tablo) döndürür. */
(function (root) {
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Bir ipucunun içeriği: görsel varsa görsel, yoksa metin.
  function clueInner(text, img, isFlag) {
    if (img) {
      return '<img src="' + esc(img) + '" alt="" class="' + (isFlag ? 'bayrak' : 'gorsel') + '">';
    }
    return '<span class="metin">' + esc(text) + '</span>';
  }

  function renderCell(cell) {
    if (!cell) return '<td class="bos"></td>';

    if (cell.is_playable) {
      return '<td class="harf"><span class="cevap">' + esc(cell.solution_letter) + '</span></td>';
    }

    // İç kısımdaki ipucu (kırılma) hücresi: 1 ya da 2 ipucu
    if (cell.clues) {
      var right = null, down = null, i;
      for (i = 0; i < cell.clues.length; i++) {
        if (cell.clues[i].direction === 'right') right = cell.clues[i];
        else down = cell.clues[i];
      }
      if (right && down) {
        return '<td class="ipucu"><div class="bolunmus">' +
          '<div class="yarim ust ok-sag">' + clueInner(right.text, right.image_url, right.is_flag) + '</div>' +
          '<div class="yarim alt ok-asagi">' + clueInner(down.text, down.image_url, down.is_flag) + '</div>' +
          '</div></td>';
      }
      var one = right || down;
      if (one) {
        return '<td class="ipucu"><div class="tam ' + (right ? 'ok-sag' : 'ok-asagi') + '">' +
          clueInner(one.text, one.image_url, one.is_flag) + '</div></td>';
      }
      return '<td class="ipucu bos-ipucu"></td>';
    }

    // Kenar (üst satır / sol sütun) ipucu hücresi
    var arrow = cell.row === 0 ? 'ok-asagi' : 'ok-sag';
    if (cell.clue_text || cell.clue_image_url) {
      return '<td class="ipucu"><div class="tam ' + arrow + '">' +
        clueInner(cell.clue_text, cell.clue_image_url, cell.is_flag) + '</div></td>';
    }
    // Tek harfli cevap olmadığı için ipucu verilmeyen kenar hücresi
    return '<td class="ipucu bos-ipucu"></td>';
  }

  function renderPuzzle(p, no) {
    var map = {}, i;
    for (i = 0; i < p.cells.length; i++) {
      map[p.cells[i].row + ',' + p.cells[i].col] = p.cells[i];
    }
    var html = '<section class="bulmaca"><h2>Bulmaca ' + no +
      ' <small>' + p.kelime_sayisi + ' kelime &middot; ' + esc(String(p.id).substr(0, 8)) + '</small></h2>' +
      '<table class="izgara">';
    for (var r = 0; r < p.rows; r++) {
      html += '<tr>';
      for (var c = 0; c < p.cols; c++) {
        html += renderCell(map[r + ',' + c]);
      }
      html += '</tr>';
    }
    return html + '</table></section>';
  }

  root.renderPuzzle = renderPuzzle;
  if (typeof module !== 'undefined') module.exports = { renderPuzzle: renderPuzzle };
})(typeof window !== 'undefined' ? window : globalThis);
