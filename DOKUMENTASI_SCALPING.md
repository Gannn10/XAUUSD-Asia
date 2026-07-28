# 📘 XAU/USD Scalping Bot — Sesi Asia
**Versi:** 1.0.0
**Author:** Gani
**Jam Aktif:** 07:00 – 15:00 WIB (UTC+7)
**Timeframe:** M15
**Stack:** Python 3 · MetaTrader5 API · Pandas · TA-Lib (ta)

---

## 🗂️ Daftar Isi
1. [Filosofi Scalping Sesi Asia](#1-filosofi-scalping-sesi-asia)
2. [Karakteristik Pasar XAU Sesi Asia](#2-karakteristik-pasar-xau-sesi-asia)
3. [Struktur File Project](#3-struktur-file-project)
4. [Alur Kerja Bot (Flowchart)](#4-alur-kerja-bot-flowchart)
5. [Pilar 1 — Bollinger Bands (Range Detector)](#5-pilar-1--bollinger-bands-range-detector)
6. [Pilar 2 — RSI (Momentum Konfirmasi)](#6-pilar-2--rsi-momentum-konfirmasi)
7. [Pilar 3 — Stochastic Oscillator (Timing Presisi)](#7-pilar-3--stochastic-oscillator-timing-presisi)
8. [Pilar 4 — Pivot Points Daily (Batas Hard S/R)](#8-pilar-4--pivot-points-daily-batas-hard-sr)
9. [Pilar 5 — ATR (Sizing SL & TP)](#9-pilar-5--atr-sizing-sl--tp)
10. [Filter Sesi Waktu (Asia Session Guard)](#10-filter-sesi-waktu-asia-session-guard)
11. [Logika Entry Lengkap](#11-logika-entry-lengkap)
12. [Perbedaan Scalping vs Swing Bot](#12-perbedaan-scalping-vs-swing-bot)
13. [Risk Management Scalping](#13-risk-management-scalping)
14. [Penjelasan Parameter Config](#14-penjelasan-parameter-config)
15. [Checklist Sebelum Deploy](#15-checklist-sebelum-deploy)

---

## 1. Filosofi Scalping Sesi Asia

Scalping dan swing adalah **dua permainan yang berbeda total**, bahkan di aset yang sama.

```
SWING BOT               SCALPING BOT
────────────────────    ────────────────────
"Ikut arus besar"       "Manfaatkan range"
Tunggu trend kuat       Tidak butuh trend
TP jauh, SL lebar       TP kecil, SL ketat
1–5 trade/minggu        3–8 trade/hari
Profit per trade besar  Profit per trade kecil
                        tapi frekuensi tinggi
```

### Prinsip Utama Scalping Sesi Asia

> **"Sesi Asia tidak trending — dia ranging. Tugas kita bukan mengejar, tapi menunggu di ujung range."**

```
Harga XAU sesi Asia:

$2,360 ──────────────────────────── ← Batas Atas Range (SELL area)
         ╭───╮     ╭───╮
$2,350  ╱     ╲   ╱     ╲
       ╱       ╲ ╱       ╲
$2,340 ─────────╳─────────── ← Tengah Range
       ╲       ╱ ╲       ╱
$2,330  ╲     ╱   ╲     ╱
         ╰───╯     ╰───╯
$2,320 ──────────────────────────── ← Batas Bawah Range (BUY area)

Strategi: BUY di bawah, SELL di atas, TP di tengah range.
```

---

## 2. Karakteristik Pasar XAU Sesi Asia

### Jam Aktif & Transisi Sesi

```
WIB (UTC+7)          Sesi         Karakteristik XAU
───────────────────────────────────────────────────
07:00 – 09:00        Asia Open    Mulai bergerak, range terbentuk
09:00 – 13:00        Asia Mid     Range paling stabil → zona scalping terbaik
13:00 – 15:00        Asia Close   Mulai ada persiapan menjelang London
15:00 – 21:00        London       Volatilitas naik, scalping berbahaya
20:00 – 00:00        New York     Pergerakan besar, scalping tidak direkomendasikan
```

> ⭐ **Zona emas scalping: 09:00 – 13:00 WIB**
> Bot tetap aktif 07:00–15:00, tapi sinyal terkuat biasanya muncul di jam ini.

### Statistik Umum Sesi Asia XAU

```
Average Daily Range (ADR) sesi Asia : $15 – $35
Average Range per M15 candle        : $3  – $8
Spread typical XAU sesi Asia        : $0.30 – $0.50
Karakteristik dominan               : Ranging / Mean Reversion
Frekuensi false breakout            : Tinggi (hati-hati!)
```

---

## 3. Struktur File Project

```
/algo-trading-bot
│
├── requirements.txt          → Daftar library (sama dengan swing bot)
│
├── config_swing.py           → Parameter khusus swing bot (H1)
├── config_scalping.py        → Parameter khusus scalping bot (M15) ← BARU
│
├── swing_bot.py              → Bot swing H1 (versi sebelumnya)
├── scalping_bot.py           → Bot scalping M15 sesi Asia ← BARU
│
├── trading_swing.log         → Log khusus swing bot
└── trading_scalping.log      → Log khusus scalping bot ← BARU
```

**Kenapa config dipisah per bot?**

Swing dan scalping punya parameter yang sangat berbeda. Kalau digabung dalam satu config, rawan salah edit dan sulit dibaca. Pisah = lebih aman.

**Bisa jalan bersamaan?**

Ya, tapi **jangan dulu** di fase awal. Jalankan scalping bot sendiri sampai terbukti profitable. Nanti kalau sudah stabil, baru jalankan keduanya paralel dengan MAGIC_NUMBER berbeda agar MT5 bisa membedakan order dari masing-masing bot.

---

## 4. Alur Kerja Bot (Flowchart)

```
START
  │
  ▼
[Inisialisasi MT5]
  │
  ▼
[Deteksi Filling Mode Broker]
  │
  ▼
┌──────────────────────────────────────────────────┐
│                  LOOP UTAMA                      │
│                                                  │
│  ┌─────────────────────────────────────────┐     │
│  │  CEK JAM — APAKAH SESI ASIA AKTIF?      │     │
│  │  07:00 – 15:00 WIB                      │     │
│  └──────────────┬──────────────────────────┘     │
│                 │                                │
│          YA ←──┴──► TIDAK                        │
│          │               │                       │
│          │           Sleep 5 menit               │
│          │           (tunggu sesi Asia)           │
│          ▼                                       │
│  Ambil data M15 (150 candle)                     │
│  Hitung: BB, RSI, Stochastic, ATR                │
│  Ambil Pivot Daily (S1, R1, PP)                  │
│          │                                       │
│          ▼                                       │
│  Apakah harga sedang RANGING?                    │
│  (BB Width < threshold)                          │
│     │              │                             │
│    YA             TIDAK                          │
│     │              │                             │
│     │         Log: "Market trending,             │
│     │          skip scalping"                    │
│     │              │                             │
│     ▼              │                             │
│  Ada posisi terbuka?                             │
│     │         │                                  │
│    YA        TIDAK                               │
│     │         │                                  │
│     │         ▼                                  │
│     │   Cek kondisi BUY:                         │
│     │   BB Lower + RSI + Stoch                   │
│     │         │                                  │
│     │   Cek kondisi SELL:                        │
│     │   BB Upper + RSI + Stoch                   │
│     │         │                                  │
│     │   Sinyal valid?                            │
│     │    │         │                             │
│     │   YA        TIDAK                          │
│     │    │         │                             │
│     │  Kirim order │                             │
│     │    │         │                             │
│     └────┴─────────┘                             │
│          │                                       │
│    Sleep ke M15 candle berikutnya                │
└──────────────────────────────────────────────────┘
  │
  ▼
[Ctrl+C → MT5 Shutdown → STOP]
```

---

## 5. Pilar 1 — Bollinger Bands (Range Detector)

### Apa itu Bollinger Bands?

Bollinger Bands terdiri dari **3 garis** yang membentuk "envelope" di sekitar harga:
- **Upper Band** → batas atas statistik harga
- **Middle Band** → SMA 20 (rata-rata harga)
- **Lower Band** → batas bawah statistik harga

Lebar banda mencerminkan **volatilitas pasar saat ini**.

### Rumus Bollinger Bands

**Langkah 1 — Hitung Middle Band (SMA 20):**
```
Middle Band = (Close₁ + Close₂ + ... + Close₂₀) / 20
```

**Langkah 2 — Hitung Standard Deviation (σ):**
```
σ = √( Σ(Close_i - Middle Band)² / N )

Artinya: seberapa jauh harga menyimpang dari rata-ratanya
```

**Langkah 3 — Hitung Upper dan Lower Band:**
```
Upper Band = Middle Band + (2 × σ)
Lower Band = Middle Band - (2 × σ)
```

**Kenapa 2σ?**
```
Secara statistik (distribusi normal):
  1σ → 68.2% harga berada di dalam band
  2σ → 95.4% harga berada di dalam band  ← yang dipakai
  3σ → 99.7% harga berada di dalam band

Artinya: harga yang menyentuh Upper/Lower Band (2σ)
adalah kejadian yang hanya terjadi ~4.6% waktu.
Ini zona "ekstrem" yang sering menjadi titik balik.
```

---

### Dua Fungsi BB di Bot Ini

**Fungsi 1 — Deteksi Kondisi Ranging (BB Width)**

Sebelum entry, bot harus memastikan pasar sedang ranging, bukan trending. Caranya dengan mengukur lebar Bollinger Bands:

```
BB Width = (Upper Band - Lower Band) / Middle Band × 100

BB Width kecil  → range sempit → pasar ranging  → SCALPING VALID ✅
BB Width besar  → range lebar  → pasar trending → SKIP, berbahaya ❌
```

**Contoh nyata:**
```
Upper Band  = $2,360
Lower Band  = $2,330
Middle Band = $2,345

BB Width = ($2,360 - $2,330) / $2,345 × 100 = 1.28%

Jika BB_WIDTH_MAX = 1.5%
→ 1.28% < 1.5% → pasar ranging → bot aktif ✅
```

**Fungsi 2 — Zona Entry (BB Touch)**

```
Harga menyentuh Lower Band → potensi BUY (harga terlalu murah secara statistik)
Harga menyentuh Upper Band → potensi SELL (harga terlalu mahal secara statistik)
Target TP                  → Middle Band (harga kembali ke rata-rata)
```

```
Upper Band ─────────────────────────── ← SELL di sini
                  ↕ range
Middle Band ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  ← TARGET TP
                  ↕ range
Lower Band  ─────────────────────────── ← BUY di sini
```

### Setting di Config
```python
BB_PERIOD    = 20     # Periode SMA untuk middle band
BB_STD_DEV   = 2.0    # Multiplier standard deviation (standar)
BB_WIDTH_MAX = 1.5    # Maksimal BB Width (%) agar dianggap ranging
                      # Naikkan jika sinyal terlalu jarang
                      # Turunkan jika sinyal terlalu banyak/noisy
```

---

## 6. Pilar 2 — RSI (Momentum Konfirmasi)

### Peran RSI di Scalping vs Swing

Di swing bot, RSI dipakai dengan threshold **30/70** (sinyal kuat tapi jarang).
Di scalping bot, threshold dilonggarkan menjadi **40/60** karena:

```
Scalping sesi Asia:
  Range pergerakan kecil → RSI jarang sampai ekstrem 30/70
  Kalau tunggu RSI < 30  → sinyal muncul sangat jarang
  Solusi: gunakan 40/60 sebagai "early warning" momentum
```

### Rumus RSI (sama dengan swing bot)

```
RS  = Average Gain / Average Loss  (selama 14 periode)
RSI = 100 - (100 / (1 + RS))
```

### Interpretasi RSI di Scalping

| RSI | Kondisi | Aksi |
|-----|---------|------|
| < 40 | Momentum melemah (oversold ringan) | Dukung BUY |
| 40 – 60 | Netral | Tidak ada aksi |
| > 60 | Momentum menguat (overbought ringan) | Dukung SELL |

### Setting di Config
```python
RSI_PERIOD          = 14   # Tetap sama
RSI_OVERSOLD_SCALP  = 40   # Lebih longgar dari swing (30)
RSI_OVERBOUGHT_SCALP = 60  # Lebih longgar dari swing (70)
```

---

## 7. Pilar 3 — Stochastic Oscillator (Timing Presisi)

### Mengapa Stochastic Ditambahkan?

RSI sendiri tidak cukup untuk scalping — terlalu lambat untuk M15.
Stochastic lebih **sensitif dan cepat bereaksi**, cocok untuk timing entry yang presisi di sesi Asia.

Kombinasi RSI + Stochastic memberikan **double konfirmasi momentum**:
```
RSI konfirmasi  → "apakah area ini oversold/overbought?"
Stochastic      → "apakah momentum pembalikan sudah mulai?"
```

### Rumus Stochastic Oscillator

**%K (Stochastic cepat):**
```
%K = ((Close - Lowest Low(N)) / (Highest High(N) - Lowest Low(N))) × 100

N         = periode lookback (default: 14)
Close     = harga penutupan candle sekarang
Lowest Low(N)   = harga low terendah selama N candle
Highest High(N) = harga high tertinggi selama N candle

Artinya: posisi harga saat ini relatif terhadap range N candle terakhir
         0  = harga di titik terendah range
         100 = harga di titik tertinggi range
```

**%D (Stochastic lambat / signal line):**
```
%D = SMA(%K, 3)   → rata-rata %K selama 3 periode

%D adalah "signal line" — lebih halus dari %K
```

### Cara Membaca Stochastic

```
%K dan %D < 20  → Oversold  → potensi naik → dukung BUY
%K dan %D > 80  → Overbought → potensi turun → dukung SELL

Sinyal TERKUAT = %K memotong %D dari bawah (di zona < 20) → BUY
                 %K memotong %D dari atas  (di zona > 80) → SELL
```

**Contoh visual crossover:**
```
SINYAL BUY (bullish crossover di zona oversold):

  %K ────╮          ╭──── %K naik memotong %D
  %D ─────╲────────╱───── dari bawah
            ╲      ↑
             ╲  crossover di sini
    20 ────────────────────────────── garis oversold
              ╲    ╱
    10 ─────── ╲  ╱ ──────────────── zona oversold
                ╲╱
```

### Setting di Config
```python
STOCH_K_PERIOD  = 14   # Periode %K
STOCH_D_PERIOD  = 3    # Periode smoothing %D
STOCH_OVERSOLD  = 20   # Threshold BUY
STOCH_OVERBOUGHT = 80  # Threshold SELL
```

---

## 8. Pilar 4 — Pivot Points Daily (Batas Hard S/R)

### Peran Pivot di Scalping

Di scalping, Pivot Points digunakan sedikit berbeda dari swing bot:

```
SWING BOT              SCALPING BOT
─────────────────────  ──────────────────────────────
S1 = zona entry BUY    S1 = batas bawah range yang tidak boleh ditembus
R1 = zona entry SELL   R1 = batas atas range yang tidak boleh ditembus
PP = tidak dipakai     PP = target TP tengah (mean reversion target)
```

### Tiga Fungsi Pivot di Scalping Bot

**Fungsi 1 — Konfirmasi Zona Entry**
```
Harga di dekat S1 + BB Lower terpenuhi → konfluensi BUY sangat kuat
Harga di dekat R1 + BB Upper terpenuhi → konfluensi SELL sangat kuat
```

**Fungsi 2 — Target TP (PP sebagai Magnet)**
```
Sesi Asia, harga cenderung gravitasi ke PP (Pivot Point tengah).
Jika entry BUY di S1, TP bisa dipasang di PP.
Jika entry SELL di R1, TP bisa dipasang di PP.
```

**Fungsi 3 — Hard Stop (Batas Absolut)**
```
Jika harga tembus S1 dengan signifikan → ini bukan ranging lagi
Bot harus SKIP entry, pasar mungkin akan trending turun

Jika harga tembus R1 dengan signifikan → ini bukan ranging lagi
Bot harus SKIP entry, pasar mungkin akan trending naik
```

### Rumus (sama dengan swing bot)
```
Data: High, Low, Close dari D1 sebelumnya

PP = (High + Low + Close) / 3
S1 = (PP × 2) - High
R1 = (PP × 2) - Low
```

### Setting di Config
```python
TOLERANSI_PIVOT = 2.0              # ±$2 dari S1/R1/PP
PIVOT_TIMEFRAME = mt5.TIMEFRAME_D1
GUNAKAN_PP_SEBAGAI_TP = True       # Aktifkan PP sebagai target TP alternatif
```

---

## 9. Pilar 5 — ATR (Sizing SL & TP)

### Perbedaan ATR Scalping vs Swing

```
SWING BOT               SCALPING BOT
──────────────────────  ──────────────────────
SL  = ATR × 1.5         SL  = ATR × 0.8   (lebih ketat)
TP  = ATR × 3.0         TP  = ATR × 1.0   (lebih dekat, lebih sering kena)
RR  = 1 : 2             RR  = 1 : 1.25    (lebih rendah, dikompensasi frekuensi)
```

### Kenapa TP Lebih Kecil di Scalping?

```
Sesi Asia range harian: $15 – $35
ATR M15 rata-rata     : $4  – $8

Kalau pakai TP = ATR × 3.0 = $12–$24
→ Ini sudah mendekati TOTAL range sesi Asia
→ TP tidak akan pernah tercapai!

Solusi: TP = ATR × 1.0 = $4–$8
→ Realistis untuk range M15 sesi Asia
→ Frekuensi TP tercapai jauh lebih tinggi
```

### Contoh Kalkulasi

```
Harga entry BUY : $2,330.00
ATR M15         : $6.00

SL  = $2,330.00 - ($6.00 × 0.8) = $2,325.20
TP  = $2,330.00 + ($6.00 × 1.0) = $2,336.00

Risiko  : $4.80  per lot
Potensi : $6.00  per lot
RR      : 1 : 1.25
```

### Alternatif TP: Gunakan PP Pivot

```
Jika PP Pivot lebih dekat dari ATR × 1.0:
  → Gunakan PP sebagai TP (lebih natural, level yang diperhatikan pasar)

Jika PP Pivot lebih jauh dari ATR × 1.0:
  → Gunakan ATR × 1.0 (lebih konservatif)

Bot otomatis pilih yang LEBIH DEKAT dari keduanya:
  TP = MIN(PP, ATR × 1.0)
```

### Setting di Config
```python
ATR_PERIOD        = 14
ATR_SL_MULTIPLIER = 0.8   # Lebih ketat dari swing (1.5)
ATR_TP_MULTIPLIER = 1.0   # Lebih dekat dari swing (3.0)
```

---

## 10. Filter Sesi Waktu (Asia Session Guard)

### Ini Adalah Filter Paling Penting

Tanpa filter waktu, bot akan aktif 24 jam dan **pasti rugi** saat sesi London/NY karena volatilitas tinggi menghancurkan SL yang ketat.

### Cara Kerja Filter

```python
def adalah_sesi_asia():
    """
    Cek apakah sekarang adalah jam sesi Asia
    Semua dalam WIB (UTC+7)
    """
    from datetime import datetime, time
    import pytz
    
    wib = pytz.timezone('Asia/Jakarta')
    sekarang = datetime.now(wib).time()
    
    jam_buka = time(7, 0)    # 07:00 WIB
    jam_tutup = time(15, 0)  # 15:00 WIB
    
    return jam_buka <= sekarang < jam_tutup
```

### Logika Guard di Main Loop

```python
# Di dalam loop utama:
if not adalah_sesi_asia():
    menit_ke_buka = hitung_menit_ke_sesi_asia()
    logger.info(f"Di luar sesi Asia. Bot hibernasi {menit_ke_buka} menit...")
    time.sleep(menit_ke_buka * 60)
    continue
```

### Setting di Config
```python
JAM_BUKA_ASIA  = "07:00"   # WIB
JAM_TUTUP_ASIA = "15:00"   # WIB
TIMEZONE       = "Asia/Jakarta"

# Opsional: matikan 30 menit sebelum London buka
# untuk menghindari spike sesi overlap
JAM_TUTUP_AMAN = "14:30"   # WIB (lebih aman dari 15:00)
```

---

## 11. Logika Entry Lengkap

### Pra-kondisi (wajib terpenuhi sebelum cek sinyal)

```
✅ JAM       : 07:00 – 15:00 WIB (sesi Asia aktif)
✅ RANGING   : BB Width < BB_WIDTH_MAX (pasar tidak trending)
✅ POSISI    : Tidak ada posisi terbuka untuk XAUUSD
```

---

### Kondisi BUY (semua harus terpenuhi)

```
✅ ZONA BB   : Harga ≤ Lower Band + toleransi
               (harga menyentuh batas bawah statistik)

✅ MOMENTUM  : RSI < 40
               (momentum melemah, potensi reversal naik)

✅ MOMENTUM  : Stochastic %K < 20 DAN %D < 20
               (konfirmasi oversold dari indikator kedua)

✅ TIMING    : %K memotong %D dari bawah
               (crossover bullish — momentum mulai berbalik)

✅ S/R       : Harga di atas S1 Pivot (tidak breakdown)
               (konfirmasi bahwa ini masih di dalam range)
──────────────────────────────────────────────────────
→ Entry  : BUY di harga ASK
→ SL     : ASK - (ATR × 0.8)
→ TP     : MIN(Middle Band, PP Pivot, ASK + ATR × 1.0)
→ Log    : Catat semua nilai indikator saat entry
```

---

### Kondisi SELL (semua harus terpenuhi)

```
✅ ZONA BB   : Harga ≥ Upper Band - toleransi
               (harga menyentuh batas atas statistik)

✅ MOMENTUM  : RSI > 60
               (momentum menguat berlebih, potensi reversal turun)

✅ MOMENTUM  : Stochastic %K > 80 DAN %D > 80
               (konfirmasi overbought dari indikator kedua)

✅ TIMING    : %K memotong %D dari atas
               (crossover bearish — momentum mulai berbalik)

✅ S/R       : Harga di bawah R1 Pivot (tidak breakout)
               (konfirmasi bahwa ini masih di dalam range)
──────────────────────────────────────────────────────
→ Entry  : SELL di harga BID
→ SL     : BID + (ATR × 0.8)
→ TP     : MAX(Middle Band, PP Pivot, BID - ATR × 1.0)
→ Log    : Catat semua nilai indikator saat entry
```

---

### Contoh Log Output Bot

```
2025-01-15 10:15:03 | INFO  | Sesi Asia AKTIF (10:15 WIB)
2025-01-15 10:15:03 | INFO  | XAUUSD M15 | Harga: 2329.80 | RSI: 38.2 | ATR: 5.50
2025-01-15 10:15:03 | INFO  | BB → Upper: 2358.20 | Mid: 2344.00 | Lower: 2329.80
2025-01-15 10:15:03 | INFO  | BB Width: 1.22% → Ranging ✅
2025-01-15 10:15:03 | INFO  | Stoch %K: 18.4 | %D: 22.1 → Crossover: ✅ (K memotong D dari bawah)
2025-01-15 10:15:03 | INFO  | Pivot → PP: 2345.00 | S1: 2332.00 | R1: 2358.00
2025-01-15 10:15:03 | INFO  | Harga (2329.80) > S1 (2332.00)? → ✅ Di atas S1
2025-01-15 10:15:03 | INFO  | ✅ SINYAL BUY — Semua konfluensi terpenuhi
2025-01-15 10:15:03 | INFO  | ORDER BUY BERHASIL! Tiket #10045888 | TP: 2335.30 | SL: 2325.40
```

---

## 12. Perbedaan Scalping vs Swing Bot

| Aspek | Swing Bot (H1) | Scalping Bot (M15) |
|-------|---------------|-------------------|
| **Timeframe** | H1 | M15 |
| **Jam Aktif** | 24 jam | 07:00–15:00 WIB |
| **Strategi** | Trend Following | Mean Reversion / Range |
| **Indikator Utama** | EMA 200, Fibonacci | Bollinger Bands |
| **Konfirmasi** | RSI 30/70 | RSI 40/60 + Stochastic |
| **S/R Level** | Pivot + Fib | Pivot (PP sebagai TP) |
| **ATR SL** | × 1.5 | × 0.8 |
| **ATR TP** | × 3.0 | × 1.0 |
| **Risk:Reward** | 1:2 | 1:1.25 |
| **Frekuensi** | 1–5 trade/minggu | 3–8 trade/hari |
| **Filter Trend** | EMA wajib selaras | BB Width (ranging check) |
| **MAGIC_NUMBER** | 777999 | 888111 (harus beda!) |

---

## 13. Risk Management Scalping

### Kenapa RR 1:1.25 Masih Profitable?

```
Scalping mengandalkan FREKUENSI, bukan besar profit per trade.

Simulasi 20 trade/minggu dengan win rate 55%:
  Win  : 11 trade × $6.00 = +$66.00
  Loss :  9 trade × $4.80 = -$43.20
  Net  : +$22.80 per minggu (lot 0.01)

Bandingkan swing bot (3 trade/minggu, win rate 50%):
  Win  : 1.5 trade × $3.60 = +$5.40
  Loss : 1.5 trade × $1.80 = -$2.70
  Net  : +$2.70 per minggu (lot 0.01)

Scalping lebih produktif PER MINGGU, tapi butuh disiplin lebih ketat.
```

### Aturan Tambahan Risk Management

```
MAX TRADE PER HARI  = 5
→ Kalau sudah 5 trade hari ini, bot berhenti sampai besok
→ Mencegah overtrading saat kondisi pasar jelek

MAX LOSS PER HARI   = 3 trade loss beruntun → bot pause 2 jam
→ Kalau loss 3x berturut-turut, kemungkinan kondisi market sedang jelek
→ Bot istirahat 2 jam, lalu resume

JANGAN TAMBAH POSISI
→ Tidak ada averaging down / martingale
→ 1 posisi = 1 tiket, titik
```

### Simulasi Drawdown Terburuk

```
Lot 0.01 | ATR rata-rata $6 | SL = $4.80

5 trade loss beruntun   = -$24.00
10 trade loss beruntun  = -$48.00

Untuk akun demo $500 → drawdown 10 loss = 9.6% (masih aman)
Untuk akun demo $200 → drawdown 10 loss = 24%  (waspadai!)
```

---

## 14. Penjelasan Parameter Config

```python
# config_scalping.py

import MetaTrader5 as mt5

# ── CORE ──────────────────────────────────────────────────
SYMBOL          = "XAUUSD"
TIMEFRAME       = mt5.TIMEFRAME_M15      # M15 untuk scalping
LOT_SIZE        = 0.01
MAGIC_NUMBER    = 888111                 # BEDA dari swing bot (777999)!
DEVIATION       = 20

# ── BOLLINGER BANDS ────────────────────────────────────────
BB_PERIOD       = 20                     # Periode SMA middle band
BB_STD_DEV      = 2.0                    # Multiplier std deviation
BB_WIDTH_MAX    = 1.5                    # % maksimal BB Width untuk ranging
                                         # Naikkan → lebih banyak sinyal (lebih noisy)
                                         # Turunkan → lebih sedikit sinyal (lebih selektif)
TOLERANSI_BB    = 0.5                    # ±$0.5 dari BB Upper/Lower untuk zona touch

# ── RSI ────────────────────────────────────────────────────
RSI_PERIOD           = 14
RSI_OVERSOLD_SCALP   = 40               # Lebih longgar dari swing (30)
RSI_OVERBOUGHT_SCALP = 60               # Lebih longgar dari swing (70)

# ── STOCHASTIC ─────────────────────────────────────────────
STOCH_K_PERIOD   = 14                   # Periode %K
STOCH_D_PERIOD   = 3                    # Periode smoothing %D
STOCH_OVERSOLD   = 20                   # Threshold BUY
STOCH_OVERBOUGHT = 80                   # Threshold SELL

# ── PIVOT POINTS ───────────────────────────────────────────
PIVOT_TIMEFRAME        = mt5.TIMEFRAME_D1
TOLERANSI_PIVOT        = 2.0
GUNAKAN_PP_SEBAGAI_TP  = True           # PP sebagai kandidat TP

# ── ATR ────────────────────────────────────────────────────
ATR_PERIOD        = 14
ATR_SL_MULTIPLIER = 0.8                 # Lebih ketat dari swing (1.5)
ATR_TP_MULTIPLIER = 1.0                 # Lebih dekat dari swing (3.0)

# ── SESI WAKTU ─────────────────────────────────────────────
JAM_BUKA_ASIA   = 7                     # 07:00 WIB
JAM_TUTUP_ASIA  = 15                    # 15:00 WIB (bisa ubah ke 14 untuk lebih aman)
TIMEZONE        = "Asia/Jakarta"

# ── RISK CONTROL ───────────────────────────────────────────
MAX_TRADE_PER_HARI    = 5              # Maksimal order per hari
MAX_LOSS_BERUNTUN     = 3              # Pause 2 jam setelah loss beruntun
PAUSE_SETELAH_LOSS    = 120            # Menit pause (120 menit = 2 jam)

# ── DATA ───────────────────────────────────────────────────
NUM_CANDLES     = 150                  # 150 candle M15 ≈ ~37 jam data

# ── LOGGING ────────────────────────────────────────────────
LOG_FILE        = "trading_scalping.log"
LOG_LEVEL       = "INFO"
```

---

## 15. Checklist Sebelum Deploy

### ✅ Setup Awal
- [ ] `config_scalping.py` sudah dibuat terpisah dari `config_swing.py`
- [ ] `MAGIC_NUMBER = 888111` (beda dari swing bot)
- [ ] Library `pytz` terinstall (`pip install pytz`)
- [ ] Timezone device sudah benar (WIB / UTC+7)

### ✅ Verifikasi Parameter
- [ ] `BB_WIDTH_MAX` di-test dulu secara manual di MT5 (lihat apakah sesi Asia memang ranging)
- [ ] `TOLERANSI_BB` tidak terlalu besar (jangan sampai selalu dianggap touch BB)
- [ ] `MAX_TRADE_PER_HARI` sudah ditentukan
- [ ] `JAM_TUTUP_ASIA = 14` (lebih aman) atau `15`?

### ✅ Test Sebelum Live Demo
- [ ] Jalankan bot jam 09:00 WIB, amati log apakah jam filter berjalan
- [ ] Pastikan bot DIAM di luar jam 07:00–15:00
- [ ] Cek apakah BB Width terhitung dengan benar di log
- [ ] Cek apakah Stochastic crossover terdeteksi

### ✅ Forward Testing (Minimal 2 Minggu = ~50 trade)
- [ ] Catat setiap trade: jam entry, indikator saat entry, result
- [ ] Hitung win rate per jam (09:00–11:00 vs 11:00–13:00 vs 13:00–15:00)
- [ ] Evaluasi: jam mana yang paling profitable?
- [ ] Evaluasi: `BB_WIDTH_MAX` perlu dinaikkan atau diturunkan?

### ⚠️ Hal Kritis yang Harus Diingat
- **MATIKAN bot sebelum news besar** — NFP, CPI, FOMC bisa spike menembus SL ketat
- **Sesi Asia bisa tiba-tiba volatile** saat ada berita dari China, Jepang, atau Australia
- **Spread naik saat sesi pertama buka** (07:00–08:00) — pertimbangkan mulai dari 08:00
- **Jangan ubah parameter saat bot sedang berjalan** — tutup dulu, ubah, jalankan ulang
- **Ini scalping bukan swing** — jangan ubah TP/SL secara manual karena "feeling"

---

*Dokumentasi ini adalah panduan teknis untuk forward testing pada akun demo.*
*Selalu validasi strategi dengan data nyata sebelum mempertimbangkan live trading.*
