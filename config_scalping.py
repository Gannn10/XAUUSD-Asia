"""
config_scalping.py
==================
Konfigurasi XAU/USD Scalping Bot — Sesi Asia
Broker  : Exness
Symbol  : XAUUSD
Timeframe: M15
Author  : Gani
"""

import MetaTrader5 as mt5

# ═══════════════════════════════════════════════════════════════
# CORE — Identitas Bot
# ═══════════════════════════════════════════════════════════════
SYMBOL          = "XAUUSDm"              # Exness pakai "XAUUSDm" (ada huruf m!)
TIMEFRAME       = mt5.TIMEFRAME_M15      # M15 untuk scalping sesi Asia
LOT_SIZE        = 0.01                   # Mulai kecil untuk testing
MAGIC_NUMBER    = 888111                 # BEDA dari swing bot (777999)!
DEVIATION       = 20                     # Slippage tolerance (point)

# ═══════════════════════════════════════════════════════════════
# BOLLINGER BANDS — Range Detector + Entry Zone
# ═══════════════════════════════════════════════════════════════
BB_PERIOD       = 20                     # Periode SMA middle band
BB_STD_DEV      = 2.0                    # Multiplier std deviation (standar)
BB_WIDTH_MAX    = 2.5                    # % maksimal BB Width agar dianggap ranging
                                         # Naikkan → lebih banyak sinyal (tapi noisy)
                                         # Turunkan → lebih sedikit sinyal (lebih selektif)
TOLERANSI_BB    = 10.0                   # ±$10.0 dari BB Upper/Lower untuk zona touch
                                         # Diperlebar dari 8.0 agar tangkapan entry lebih banyak
                                         # ATR saat ini ~7.5 jadi $10 = ~1.3 ATR

# ═══════════════════════════════════════════════════════════════
# RSI — Momentum Konfirmasi (lebih longgar dari swing)
# ═══════════════════════════════════════════════════════════════
RSI_PERIOD           = 14
RSI_OVERSOLD_SCALP   = 45               # Dinaikkan dari 42 → lebih mudah trigger BUY
RSI_OVERBOUGHT_SCALP = 55               # Diturunkan dari 58 → lebih mudah trigger SELL

# ═══════════════════════════════════════════════════════════════
# STOCHASTIC OSCILLATOR — Timing Presisi
# ═══════════════════════════════════════════════════════════════
STOCH_K_PERIOD   = 14                   # Periode %K
STOCH_D_PERIOD   = 3                    # Periode smoothing %D
STOCH_SMOOTH     = 3                    # Smooth %K (slow stochastic)
STOCH_OVERSOLD   = 35                   # Dinaikkan dari 30 → lebih mudah oversold BUY
STOCH_OVERBOUGHT = 65                   # Diturunkan dari 70 → lebih mudah overbought SELL
                                         # Sesi Asia XAU jarang capai ekstrem 80/20

# ═══════════════════════════════════════════════════════════════
# PIVOT POINTS DAILY — Batas Hard S/R
# ═══════════════════════════════════════════════════════════════
PIVOT_TIMEFRAME        = mt5.TIMEFRAME_D1
TOLERANSI_PIVOT        = 2.0            # ±$2 dari S1/R1/PP
GUNAKAN_PP_SEBAGAI_TP  = True           # PP sebagai kandidat TP

# ═══════════════════════════════════════════════════════════════
# ATR — Sizing SL & TP
# ═══════════════════════════════════════════════════════════════
ATR_PERIOD        = 14
ATR_SL_MULTIPLIER = 0.8                 # Lebih ketat dari swing (1.5)
ATR_TP_MULTIPLIER = 1.0                 # Lebih dekat dari swing (3.0)

# ═══════════════════════════════════════════════════════════════
# SESI WAKTU — Asia Session Guard (WIB / UTC+7)
# ═══════════════════════════════════════════════════════════════
JAM_BUKA_ASIA   = 7                     # 07:00 WIB
JAM_TUTUP_ASIA  = 14                    # 14:30 WIB (lebih aman, hindari overlap London)
JAM_TUTUP_MENIT = 30                    # Menit tutup (14:30)
TIMEZONE        = "Asia/Jakarta"

# ═══════════════════════════════════════════════════════════════
# RISK CONTROL — Pembatas Kerugian Harian
# ═══════════════════════════════════════════════════════════════
MAX_TRADE_PER_HARI    = 5               # Maksimal order per hari
MAX_LOSS_BERUNTUN     = 3               # Pause setelah loss beruntun N kali
PAUSE_SETELAH_LOSS    = 120             # Menit pause (120 menit = 2 jam)

# ═══════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME ANALYSIS (MTFA)
# ═══════════════════════════════════════════════════════════════
# Layer 1 — H1: Trend Guard (EMA 50 & EMA 200)
MTFA_H1_AKTIF       = True             # Aktifkan filter H1
H1_TIMEFRAME        = mt5.TIMEFRAME_H1
H1_NUM_CANDLES      = 250              # Butuh setidaknya 200 candle untuk EMA 200
H1_EMA_FAST_PERIOD  = 50               # Periode EMA cepat
H1_EMA_SLOW_PERIOD  = 200              # Periode EMA lambat

# Layer 3 — M5: Trigger Konfirmasi (candle M5 berbalik arah)
MTFA_M5_AKTIF       = True             # Aktifkan trigger M5
M5_TIMEFRAME        = mt5.TIMEFRAME_M5
M5_NUM_CANDLES      = 500               # 30 candle M5 ≈ 2.5 jam data
                                       # Trigger SELL: candle M5 terakhir bearish (close < open)
                                       # Trigger BUY:  candle M5 terakhir bullish (close > open)

# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════
NUM_CANDLES     = 150                   # 150 candle M15 ≈ ~37 jam data

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════
LOG_FILE        = "trading_scalping.log"
LOG_LEVEL       = "INFO"

# ═══════════════════════════════════════════════════════════════
# LOOP INTERVAL
# ═══════════════════════════════════════════════════════════════
SLEEP_CANDLE    = 2                     # Cek sinyal setiap 2 detik dalam candle aktif
SLEEP_LUAR_SESI = 300                   # Sleep 5 menit saat di luar sesi Asia

# ═══════════════════════════════════════════════════════════════
# NOTION INTEGRATION
# ═══════════════════════════════════════════════════════════════
ENABLE_NOTION_LOG  = True
NOTION_API_KEY     = ""
NOTION_PAGE_ID     = "379bbb728f1480c9abb2fbe342e866ea"

# ═══════════════════════════════════════════════════════════════
# MACHINE LEARNING (XGBOOST)
# ═══════════════════════════════════════════════════════════════
ML_CONFIDENCE_THRESHOLD = 0.60       # Minimum probabilitas AI untuk open posisi

# ═══════════════════════════════════════════════════════════════
# LLM AGENT (AGENTIC TRADING)
# ═══════════════════════════════════════════════════════════════
OPENROUTER_API_KEY = ""
LLM_TIMEOUT = 5.0                    # Detik maksimal tunggu balasan dari API LLM
