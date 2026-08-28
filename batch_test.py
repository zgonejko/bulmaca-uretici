import sys, random, time
sys.path.insert(0, '/home/claude/puzzle-generator')
from word_bank import WordBank
from slot_filler import fill_grid
from dynamic_template_v2 import generate_dynamic_slots_v2

wb = WordBank('/mnt/user-data/uploads/Kitap_Kisa_Cevaplar_Basta_-_Kopya.xlsx')

def generate_one_puzzle(max_template_tries=25):
    for attempt in range(max_template_tries):
        rng = random.Random()
        slots, breaks, row_b, col_b = generate_dynamic_slots_v2(rng)
        grid = fill_grid(slots, wb, max_tries_per_slot=50, max_backtracks=30000)
        if grid is not None:
            return grid, slots, breaks, attempt + 1
    return None, None, None, max_template_tries

N = 30
results = []
start = time.time()
for i in range(N):
    t0 = time.time()
    grid, slots, breaks, tries = generate_one_puzzle()
    elapsed = time.time() - t0
    success = grid is not None
    results.append((success, tries, elapsed, len(slots) if slots else 0, len(breaks) if breaks else 0))
    print(f"#{i+1:2d}: {'OK ' if success else 'FAIL'} | şablon denemesi: {tries:2d} | süre: {elapsed:5.2f}s | kelime sayısı: {len(slots) if slots else 0} | bölme: {len(breaks) if breaks else 0}")

total_time = time.time() - start
success_count = sum(1 for r in results if r[0])
print(f"\n=== ÖZET ===")
print(f"Başarı: {success_count}/{N} ({100*success_count/N:.0f}%)")
print(f"Toplam süre: {total_time:.1f}s, ortalama: {total_time/N:.2f}s/bulmaca")
avg_tries = sum(r[1] for r in results if r[0]) / max(success_count,1)
print(f"Ortalama şablon denemesi (başarılı olanlarda): {avg_tries:.1f}")
