# Update Filter H1 ke EMA Trend

Ide Anda sangat bagus dan **sangat bisa dilakukan**! 
Daripada memblokir *semua* trade saat H1 volatile/trending (menggunakan BB Width), kita akan ubah logikanya:
- Jika H1 Uptrend (EMA 50 > EMA 200) -> Bot **Boleh BUY**, tapi **Blokir SELL**
- Jika H1 Downtrend (EMA 50 < EMA 200) -> Bot **Boleh SELL**, tapi **Blokir BUY**

## Proposed Changes

### [MODIFY] `config_scalping.py`
Mengganti parameter konfigurasi H1 dari Bollinger Bands ke parameter EMA.

**Perubahan Konfigurasi:**
- `H1_NUM_CANDLES` dinaikkan menjadi `250` (karena kita butuh minimal 200 candle data historis H1 untuk menghitung EMA 200 dengan akurat).
- Menghapus parameter `H1_BB_PERIOD`, `H1_BB_STD_DEV`, dan `H1_BB_WIDTH_MAX`.
- Menambahkan parameter `H1_EMA_FAST_PERIOD = 50` dan `H1_EMA_SLOW_PERIOD = 200`.

### [MODIFY] `scalping_bot.py`
Mengubah fungsi pengecekan H1 dan logika entry.

**Detail Modifikasi:**
1.  **Fungsi `cek_h1_ranging` dihapus** dan diganti dengan fungsi baru `cek_h1_trend(df_h1)` yang menggunakan Pandas EWM (Exponential Weighted Moving Average) untuk menghitung EMA 50 dan EMA 200.
2.  **Blok `Pra-Kondisi 2` diubah:** Saat ini bot langsung me-return `state` (skip iterasi) jika H1 ranging bernilai false. Ini akan dihapus, jadi bot tidak akan memblokir secara global.
3.  **Logika Sinyal BUY:** Menambahkan validasi `h1_buy_ok`. Jika `h1["trend"] == "DOWN"`, maka `h1_buy_ok = False` dan bot mencetak log `[SKIP-H1] Trend H1 sedang DOWN, skip sinyal BUY.`.
4.  **Logika Sinyal SELL:** Menambahkan validasi `h1_sell_ok`. Jika `h1["trend"] == "UP"`, maka `h1_sell_ok = False` dan bot mencetak log `[SKIP-H1] Trend H1 sedang UP, skip sinyal SELL.`.

---

## Verification Plan

### Manual Verification
- Menjalankan bot dan mengamati log di terminal.
- Memastikan log menampilkan status Trend H1 beserta nilai EMA 50 dan EMA 200.
- Memastikan bahwa jika tren H1 adalah UP, bot tidak melakukan SELL meskipun sinyal M15 valid, dan sebaliknya.
