"""Daha önce üretilmiş bulmacaların 'anchor' çiftini (en üstteki 6 harfli +
en soldaki 8 harfli kelime) kalıcı olarak saklar. Bu ikili bulmacanın geri
kalanını neredeyse tamamen belirlediği için, aynı ikilinin tekrar
kullanılmasını engellemek, iki farklı çalıştırmada aynı/çok benzer bir
bulmacanın üretilmesini büyük ölçüde önlüyor.

Kayıt, kelime bankasıyla AYNI Excel dosyasının ayrı bir SAYFASINDA
("Uretilen_Bulmacalar") tutulur - JSON gibi ayrı bir dosya değil, tek bir
yerde (Excel'de) her şeyi bir arada tutmak için. Excel'in kendisine yeni
kelime/görsel eklemeniz bu sayfayı ETKİLEMEZ - siz elle silmediğiniz sürece
kalıcı kalır, üretici dosyasını her çalıştırdığınızda üstüne eklenir.
"""
import os
import openpyxl

SHEET_NAME = 'Uretilen_Bulmacalar'


def load_used_anchors(xlsx_path):
    if not os.path.exists(xlsx_path):
        return set()
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            return set()
        ws = wb[SHEET_NAME]
        anchors = set()
        for row in ws.iter_rows(min_row=2, max_col=2, values_only=True):
            if row and row[0] and row[1]:
                anchors.add((str(row[0]).strip().upper(), str(row[1]).strip().upper()))
        return anchors
    finally:
        wb.close()


def save_used_anchor(row1_word, col1_word, xlsx_path):
    """Yeni üretilen bir bulmacanın anchor çiftini kayda EKLER (mevcut
    kayıtları ve Excel'deki diğer sayfaları etkilemez)."""
    wb = openpyxl.load_workbook(xlsx_path)
    if SHEET_NAME not in wb.sheetnames:
        ws = wb.create_sheet(SHEET_NAME)
        ws.append(['Row1_6Harfli', 'Col1_8Harfli'])
    else:
        ws = wb[SHEET_NAME]
    ws.append([row1_word, col1_word])
    wb.save(xlsx_path)
    wb.close()
