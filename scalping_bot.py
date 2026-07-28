"""
scalping_bot.py
===============
XAU/USD Scalping Bot - Sesi Asia (07:00 - 14:30 WIB)
Broker   : Exness
Strategy : Mean Reversion / Range Scalping
Pilar    : BB + RSI + Stochastic + Pivot Points + ATR
Timeframe: M15
Author   : Gani
"""

import io
import time
import logging
import sys
from datetime import datetime, timedelta

# Fix encoding Windows terminal agar tidak error karakter khusus
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pytz
import numpy as np
import pandas as pd
import pickle
import xgboost as xgb
import polars as pl
from feature_eng import FeatureEngineer
from smc_polars import SMCAnalyzer

import MetaTrader5 as mt5

import config_scalping as cfg
from regime_detector import detect_market_regime

# Import Modul AI Agentic
from agent_deepseek import get_macro_bias
from agent_hermes import evaluate_execution
from memory_rag import retrieve_relevant_memory, save_trade_memory

# Global Cache untuk DeepSeek agar tidak dipanggil tiap detik
LAST_DEEPSEEK_TIME = 0
CURRENT_MACRO_BIAS = {"bias": "NEUTRAL", "confidence": 0.5, "reason": "Init"}

# ===============================================================
# SETUP LOGGING
# ===============================================================
def setup_logging():
    """Konfigurasi logging ke file dan console sekaligus."""
    fmt = "%(asctime)s | %(levelname)-5s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # StreamHandler dengan UTF-8 untuk Windows
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt))

    file_handler = logging.FileHandler(cfg.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))

    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.LOG_LEVEL))
    root.addHandler(console_handler)
    root.addHandler(file_handler)


logger = logging.getLogger(__name__)


# ===============================================================

# ===============================================================
# MACHINE LEARNING SETUP
# ===============================================================
ML_MODEL = None
ML_FEATURES = []
FE = FeatureEngineer()
SMC = SMCAnalyzer()

def load_ml_model():
    global ML_MODEL, ML_FEATURES
    model_path = "backtests/ml_v3/xgboost_model_v3.pkl"
    try:
        import os
        if not os.path.exists(model_path):
            logger.error(f"[ML] Model file not found: {model_path}")
            return False
            
        with open(model_path, "rb") as f:
            model_data = pickle.load(f)
            ML_MODEL = model_data["xgb_model"]
            ML_FEATURES = model_data["feature_names"]
        logger.info(f"[ML] Model loaded successfully from {model_path}")
        logger.info(f"[ML] Expected features: {len(ML_FEATURES)}")
        return True
    except Exception as e:
        logger.error(f"[ML] Failed to load model: {e}")
        return False

# INISIALISASI MT5
# ===============================================================
def init_mt5():
    """Inisialisasi koneksi ke MetaTrader 5."""
    if not mt5.initialize():
        logger.error(f"Gagal inisialisasi MT5! Error: {mt5.last_error()}")
        sys.exit(1)

    account = mt5.account_info()
    logger.info("=" * 60)
    logger.info("  XAU/USD SCALPING BOT - SESI ASIA")
    logger.info("=" * 60)
    logger.info(f"  Broker   : {account.company}")
    logger.info(f"  Akun     : {account.login}")
    logger.info(f"  Balance  : ${account.balance:.2f}")
    logger.info(f"  Leverage : 1:{account.leverage}")
    logger.info(f"  Symbol   : {cfg.SYMBOL}")
    logger.info(f"  Timeframe: M15")
    logger.info(f"  Lot Size : {cfg.LOT_SIZE}")
    logger.info(f"  Magic    : {cfg.MAGIC_NUMBER}")
    logger.info("=" * 60)


def shutdown_mt5():
    """Tutup koneksi MT5 dengan bersih."""
    mt5.shutdown()
    logger.info("MT5 shutdown. Bot berhenti.")


def detect_filling_mode():
    """
    Deteksi otomatis filling mode yang didukung broker (Exness).
    Return filling type yang akan dipakai untuk order.
    """
    symbol_info = mt5.symbol_info(cfg.SYMBOL)
    if symbol_info is None:
        logger.error(f"Symbol {cfg.SYMBOL} tidak ditemukan di MT5!")
        logger.error("Cek nama symbol di Market Watch MT5 (mungkin XAUUSDm atau XAUUSD)")
        sys.exit(1)

    filling = symbol_info.filling_mode
    if filling & mt5.ORDER_FILLING_IOC:
        logger.info("Filling mode: IOC (Immediate or Cancel)")
        return mt5.ORDER_FILLING_IOC
    elif filling & mt5.ORDER_FILLING_FOK:
        logger.info("Filling mode: FOK (Fill or Kill)")
        return mt5.ORDER_FILLING_FOK
    else:
        logger.info("Filling mode: RETURN (default)")
        return mt5.ORDER_FILLING_RETURN


# ===============================================================
# FILTER SESI WAKTU
# ===============================================================
def adalah_sesi_asia():
    """
    Cek apakah sekarang adalah jam sesi Asia (WIB).
    Returns (bool, str) -> (aktif, pesan info)
    """
    wib = pytz.timezone(cfg.TIMEZONE)
    sekarang = datetime.now(wib)
    jam = sekarang.hour
    menit = sekarang.minute

    waktu_sekarang_menit = jam * 60 + menit
    waktu_buka_menit = cfg.JAM_BUKA_ASIA * 60
    waktu_tutup_menit = cfg.JAM_TUTUP_ASIA * 60 + cfg.JAM_TUTUP_MENIT

    aktif = waktu_buka_menit <= waktu_sekarang_menit < waktu_tutup_menit
    info = f"{jam:02d}:{menit:02d} WIB"
    return aktif, info


def is_waktu_aman_entry():
    """
    Cek apakah masih aman untuk entry (bukan 15 menit terakhir sesi).
    Hindari entry di penghujung sesi karena:
    - Tidak cukup waktu untuk TP tercapai
    - Noise tinggi menjelang transisi ke sesi London
    Returns (bool, str) -> (aman, pesan info)
    """
    wib = pytz.timezone(cfg.TIMEZONE)
    sekarang = datetime.now(wib)
    waktu_sekarang_menit = sekarang.hour * 60 + sekarang.minute
    waktu_tutup_menit    = cfg.JAM_TUTUP_ASIA * 60 + cfg.JAM_TUTUP_MENIT

    # Blokir entry 15 menit sebelum sesi tutup
    BUFFER_MENIT = 15
    batas_entry  = waktu_tutup_menit - BUFFER_MENIT

    aman = waktu_sekarang_menit < batas_entry
    if not aman:
        sisa = waktu_tutup_menit - waktu_sekarang_menit
        return False, f"[NO-ENTRY] {sisa} menit terakhir sesi — terlalu dekat tutup, skip entry."
    return True, ""


def menit_ke_sesi_asia():
    """Hitung berapa menit sampai sesi Asia berikutnya buka."""
    wib = pytz.timezone(cfg.TIMEZONE)
    sekarang = datetime.now(wib)
    buka_besok = sekarang.replace(
        hour=cfg.JAM_BUKA_ASIA, minute=0, second=0, microsecond=0
    )
    if sekarang >= buka_besok:
        buka_besok += timedelta(days=1)
    delta = (buka_besok - sekarang).total_seconds() / 60
    return int(delta)


# ===============================================================
# AMBIL DATA MARKET
# ===============================================================
def ambil_data_m15():
    """
    Ambil candle M15 dari MT5.
    Returns DataFrame dengan kolom: open, high, low, close, volume
    """
    rates = mt5.copy_rates_from_pos(cfg.SYMBOL, cfg.TIMEFRAME, 0, cfg.NUM_CANDLES)
    if rates is None or len(rates) < 50:
        logger.warning("Data M15 tidak cukup atau gagal diambil.")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df


def ambil_data_h1():
    """
    [MTFA Layer 1] Ambil candle H1 untuk validasi ranging di timeframe lebih besar.
    Returns DataFrame | None
    """
    rates = mt5.copy_rates_from_pos(cfg.SYMBOL, cfg.H1_TIMEFRAME, 0, cfg.H1_NUM_CANDLES)
    if rates is None or len(rates) < 25:
        logger.warning("Data H1 tidak cukup atau gagal diambil.")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df


def ambil_data_m5():
    """
    [MTFA Layer 3] Ambil candle M5 untuk trigger konfirmasi entry.
    Returns DataFrame | None
    """
    rates = mt5.copy_rates_from_pos(cfg.SYMBOL, cfg.M5_TIMEFRAME, 0, cfg.M5_NUM_CANDLES)
    if rates is None or len(rates) < 5:
        logger.warning("Data M5 tidak cukup atau gagal diambil.")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df


def ambil_data_d1():
    """Ambil candle D1 kemarin untuk kalkulasi Pivot Points."""
    rates = mt5.copy_rates_from_pos(cfg.SYMBOL, cfg.PIVOT_TIMEFRAME, 1, 1)
    if rates is None or len(rates) == 0:
        return None
    return pd.DataFrame(rates)


# ===============================================================
# KALKULASI INDIKATOR
# ===============================================================
def hitung_bollinger_bands(df):
    """
    Hitung Bollinger Bands (20, 2.0).
    Returns dict: upper, middle, lower, width
    """
    close = df["close"]
    middle = close.rolling(cfg.BB_PERIOD).mean()
    std = close.rolling(cfg.BB_PERIOD).std()
    upper = middle + (cfg.BB_STD_DEV * std)
    lower = middle - (cfg.BB_STD_DEV * std)
    bb_width = ((upper - lower) / middle * 100).iloc[-1]

    return {
        "upper":  upper.iloc[-1],
        "middle": middle.iloc[-1],
        "lower":  lower.iloc[-1],
        "width":  bb_width,
    }


def hitung_rsi(df):
    """
    Hitung RSI 14 periode.
    Returns float: nilai RSI candle terakhir
    """
    close = df["close"]
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=cfg.RSI_PERIOD - 1, min_periods=cfg.RSI_PERIOD).mean()
    avg_loss = loss.ewm(com=cfg.RSI_PERIOD - 1, min_periods=cfg.RSI_PERIOD).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


def hitung_stochastic(df):
    """
    Hitung Stochastic Oscillator (%K dan %D).
    Returns dict: k, d, k_prev, d_prev
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    n = cfg.STOCH_K_PERIOD
    lowest_low   = low.rolling(n).min()
    highest_high = high.rolling(n).max()

    k_raw = ((close - lowest_low) / (highest_high - lowest_low)) * 100
    k = k_raw.rolling(cfg.STOCH_SMOOTH).mean()
    d = k.rolling(cfg.STOCH_D_PERIOD).mean()

    return {
        "k":      k.iloc[-1],
        "d":      d.iloc[-1],
        "k_prev": k.iloc[-2],
        "d_prev": d.iloc[-2],
    }


def hitung_atr(df):
    """
    Hitung ATR 14 periode.
    Returns float: nilai ATR candle terakhir
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(com=cfg.ATR_PERIOD - 1, min_periods=cfg.ATR_PERIOD).mean()
    return atr.iloc[-1]


def hitung_pivot_points(d1_data):
    """
    Hitung Pivot Points dari candle D1 kemarin.
    Returns dict: pp, s1, r1  |  None jika data tidak ada
    """
    if d1_data is None or len(d1_data) == 0:
        return None

    row = d1_data.iloc[0]
    h, l, c = row["high"], row["low"], row["close"]

    pp = (h + l + c) / 3
    s1 = (pp * 2) - h
    r1 = (pp * 2) - l

    return {"pp": pp, "s1": s1, "r1": r1}


def ada_crossover_bullish(stoch):
    """
    Cek momentum bullish: %K sedang bergerak NAIK.
    Lebih cocok untuk scalping M15 Asia di mana %D sering tertinggal.
    Syarat: %K > %K candle sebelumnya (momentum naik)
    """
    return stoch["k"] > stoch["k_prev"]


def ada_crossover_bearish(stoch):
    """
    Cek momentum bearish: %K sedang bergerak TURUN.
    Lebih cocok untuk scalping M15 Asia di mana %D sering tertinggal.
    Syarat: %K < %K candle sebelumnya (momentum turun)
    """
    return stoch["k"] < stoch["k_prev"]


# ===============================================================
# MTFA — LAYER 1: H1 TREND GUARD
# ===============================================================
def cek_h1_trend(df_h1):
    """
    [MTFA Layer 1] Validasi arah trend H1 menggunakan EMA 50 & 200.
    """
    if df_h1 is None or len(df_h1) < cfg.H1_EMA_SLOW_PERIOD:
        # Jika data kurang, anggap sideways agar tidak diblokir
        return {"trend": "SIDEWAYS", "ema50": 0.0, "ema200": 0.0}

    ema50  = df_h1['close'].ewm(span=cfg.H1_EMA_FAST_PERIOD, adjust=False).mean().iloc[-1]
    ema200 = df_h1['close'].ewm(span=cfg.H1_EMA_SLOW_PERIOD, adjust=False).mean().iloc[-1]
    harga  = df_h1['close'].iloc[-1]

    # Tentukan trend
    if ema50 > ema200 and harga > ema50:
        trend = "UP"
    elif ema50 < ema200 and harga < ema50:
        trend = "DOWN"
    else:
        trend = "SIDEWAYS"   # kondisi selain up/down secara tegas
    
    return {
        "trend": trend,
        "ema50": ema50,
        "ema200": ema200
    }


# ===============================================================
# MTFA — LAYER 3: M5 TRIGGER KONFIRMASI
# ===============================================================
def cek_trigger_m5(df_m5, arah):
    """
    [MTFA Layer 3] Konfirmasi entry berdasarkan arah candle M5 terakhir.
    Untuk SELL: candle M5 terakhir harus bearish (close < open) = momentum turun
    Untuk BUY:  candle M5 terakhir harus bullish (close > open) = momentum naik

    Kenapa M5?
    - M15 memberi setup, tapi timing-nya masih kasar
    - M5 memberi konfirmasi bahwa harga sudah mulai bergerak ke arah yang benar
    - Menghindari entry saat harga masih bergerak melawan (misal beli terlalu awal)

    Returns (bool, str) -> (trigger_valid, info_candle)
    """
    if df_m5 is None:
        return True, "M5 data unavailable, trigger dilewati"

    candle = df_m5.iloc[-2]  # Candle M5 yang sudah closed (bukan yang sedang berjalan)
    selisih = candle["close"] - candle["open"]
    arah_candle = "BEARISH" if selisih < 0 else "BULLISH"
    info = f"M5 candle: O={candle['open']:.2f} C={candle['close']:.2f} ({arah_candle}, {selisih:+.2f})"

    if arah == "SELL":
        return selisih < 0, info   # Bearish M5 = konfirmasi SELL
    else:  # BUY
        return selisih > 0, info   # Bullish M5 = konfirmasi BUY


# ===============================================================

# ===============================================================
# SMART BREAKEVEN
# ===============================================================
def terapkan_smart_breakeven():
    """
    Pindahkan SL ke titik Entry (BEP) jika posisi sudah running profit minimal 15 pips.
    1 pip di XAUUSD biasanya $0.1 (jika harga 2000.10) atau $1.
    Tergantung broker, kita akan pakai standar +150 point (15 pips).
    """
    positions = mt5.positions_get(symbol=cfg.SYMBOL)
    if positions is None:
        return

    for pos in positions:
        if pos.magic == cfg.MAGIC_NUMBER:
            # Hitung profit dalam pips (approximate)
            if pos.type == mt5.ORDER_TYPE_BUY:
                # Harga saat ini - harga buka
                tick = mt5.symbol_info_tick(cfg.SYMBOL)
                if tick is None: continue
                profit_points = (tick.bid - pos.price_open) / mt5.symbol_info(cfg.SYMBOL).point
                
                # Jika profit > 150 points (15 pips) dan SL masih di bawah harga open (atau belum diset)
                if profit_points >= 150 and (pos.sl == 0.0 or pos.sl < pos.price_open):
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": pos.price_open, # Pindah SL ke Entry
                        "tp": pos.tp
                    }
                    res = mt5.order_send(request)
                    if res.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"[SMART BE] Posisi BUY #{pos.ticket} diamankan di BEP.")
                        
            elif pos.type == mt5.ORDER_TYPE_SELL:
                tick = mt5.symbol_info_tick(cfg.SYMBOL)
                if tick is None: continue
                profit_points = (pos.price_open - tick.ask) / mt5.symbol_info(cfg.SYMBOL).point
                
                if profit_points >= 150 and (pos.sl == 0.0 or pos.sl > pos.price_open):
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": pos.price_open, # Pindah SL ke Entry
                        "tp": pos.tp
                    }
                    res = mt5.order_send(request)
                    if res.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"[SMART BE] Posisi SELL #{pos.ticket} diamankan di BEP.")

# CEK POSISI TERBUKA
# ===============================================================
def ada_posisi_terbuka():
    """Cek apakah ada posisi terbuka untuk symbol ini dengan magic number ini."""
    positions = mt5.positions_get(symbol=cfg.SYMBOL)
    if positions is None:
        return False
    for pos in positions:
        if pos.magic == cfg.MAGIC_NUMBER:
            return True
    return False


# ===============================================================
# KIRIM ORDER
# ===============================================================
def kirim_order(order_type, filling_mode, sl, tp, probabilitas=0.0, lot_multiplier=1.0):
    """
    Kirim order ke MT5 dengan Kelly Position Scaler dan Hermes Multiplier.
    """
    lot_size = cfg.LOT_SIZE
    # Kelly Scaler Logic
    if probabilitas > 0.85:
        lot_size = round(cfg.LOT_SIZE * 3, 2)
        logger.info(f"[KELLY] Prob {probabilitas*100:.1f}% > 85%, Lot diperbesar 3x -> {lot_size}")
    elif probabilitas > 0.70:
        lot_size = round(cfg.LOT_SIZE * 2, 2)
        logger.info(f"[KELLY] Prob {probabilitas*100:.1f}% > 70%, Lot diperbesar 2x -> {lot_size}")

    # Hermes Multiplier (dari AI Executor)
    if lot_multiplier != 1.0:
        lot_size = round(lot_size * lot_multiplier, 2)
        # Cegah lot 0
        if lot_size <= 0: lot_size = cfg.LOT_SIZE
        logger.info(f"[HERMES SCALER] Lot disesuaikan oleh AI Manager -> {lot_size}")

    """
    Kirim order BUY atau SELL ke MT5.
    Returns bool: True jika berhasil
    """
    tick = mt5.symbol_info_tick(cfg.SYMBOL)
    if tick is None:
        logger.error("Gagal ambil tick harga!")
        return False

    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
    arah  = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       cfg.SYMBOL,
        "volume":       lot_size,
        "type":         order_type,
        "price":        price,
        "sl":           round(sl, 2),
        "tp":           round(tp, 2),
        "deviation":    cfg.DEVIATION,
        "magic":        cfg.MAGIC_NUMBER,
        "comment":      f"ScalpBot-Asia-{arah}",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(
            f"[ORDER OK] {arah} | Tiket #{result.order} | "
            f"Price: {price:.2f} | SL: {sl:.2f} | TP: {tp:.2f}"
        )
        return True
    else:
        logger.error(
            f"[ORDER GAGAL] {arah} | Retcode: {result.retcode} | "
            f"Comment: {result.comment}"
        )
        return False


# ===============================================================
# ANALISIS & SINYAL
# ===============================================================
def ok_str(val):
    """Konversi bool ke string [OK] / [X] yang aman untuk Windows terminal."""
    return "[OK]" if val else "[X]"


def analisis_dan_entry(filling_mode, state):
    """
    Analisis kondisi pasar dan kirim order jika sinyal valid.
    Menggunakan 3 layer MTFA:
      Layer 1 — H1: Ranging Guard (pasar belum breakout di H1)
      Layer 2 — M15: Pattern Setup (BB + RSI + Stochastic)
      Layer 3 — M5: Trigger Konfirmasi (candle M5 berbalik arah)
    state: dict untuk tracking trade hari ini dan loss beruntun.
    Returns state yang diupdate.
    """
    # -- Ambil Data Semua Timeframe -------------------------------
    df_m15 = ambil_data_m15()
    if df_m15 is None:
        logger.warning("Data M15 tidak tersedia, skip iterasi ini.")
        return state

    df_h1  = ambil_data_h1()  if cfg.MTFA_H1_AKTIF else None
    df_m5  = ambil_data_m5()  if cfg.MTFA_M5_AKTIF else None
    df_d1  = ambil_data_d1()

    # -- ML FEATURE ENGINEERING ----------------------------------
    tick  = mt5.symbol_info_tick(cfg.SYMBOL)
    harga = (tick.ask + tick.bid) / 2 if tick else df_m15["close"].iloc[-1]
    
    prob_buy = 0.0
    prob_sell = 0.0
    
    if ML_MODEL is not None and df_m5 is not None and df_h1 is not None:
        try:
            # Prepare M5 and H1 Polars DataFrames
            df_m5_pl = pl.from_pandas(df_m5.reset_index())
            df_h1_pl = pl.from_pandas(df_h1.reset_index())
            
            # Calculate features
            df_m5_features = FE.calculate_all(df_m5_pl, include_ml_features=True)
            df_m5_features = SMC.calculate_all(df_m5_features)
            
            df_h1_features = FE.calculate_all(df_h1_pl, include_ml_features=False)
            df_h1_features = SMC.calculate_all(df_h1_features)
            
            # Select H1 features and join
            h1_cols = ["time", "close", "rsi", "atr", "bb_upper", "bb_lower", "macd", "macd_signal", "ema_20", "ema_50", "ob", "fvg", "market_structure"]
            h1_cols = [c for c in h1_cols if c in df_h1_features.columns]
            df_h1_selected = df_h1_features.select(h1_cols)
            rename_map = {c: f"h1_{c}" for c in df_h1_selected.columns if c != "time"}
            rename_map["time"] = "time"
            df_h1_selected = df_h1_selected.rename(rename_map)
            
            df_joined = df_m5_features.join_asof(df_h1_selected, on="time", strategy="backward")
            if "h1_close" in df_joined.columns and "h1_ema_20" in df_joined.columns:
                df_joined = df_joined.with_columns([
                    ((pl.col("h1_close") - pl.col("h1_ema_20")) / pl.col("h1_ema_20")).alias("h1_ema20_distance")
                ])
                
            df_joined = df_joined.fill_null(strategy="forward").fill_null(strategy="zero")
            
            # Extract latest row
            latest_features = df_joined.tail(1)
            
            # Prepare X and predict
            X = latest_features.select(ML_FEATURES).to_numpy()
            dmatrix = xgb.DMatrix(X, feature_names=ML_FEATURES)
            prob_buy = float(ML_MODEL.predict(dmatrix)[0])
            prob_sell = 1.0 - prob_buy
            
        except Exception as e:
            logger.error(f"[ML] Feature engineering failed: {e}")
            import traceback
            traceback.print_exc()

    atr = hitung_atr(df_m15)
    bb = hitung_bollinger_bands(df_m15)
    pivot = hitung_pivot_points(df_d1)

    # -- Regime Detector (HMM) -----------------------------------
    regime = detect_market_regime(df_m15)

    # -- Log Status Market ----------------------------------------
    logger.info("-" * 60)
    logger.info(
        f"{cfg.SYMBOL} | Harga: {harga:.2f} | ATR: {atr:.2f} | Regime: {regime} | "
        f"[XGBoost] Prob BUY: {prob_buy*100:.1f}% | Prob SELL: {prob_sell*100:.1f}%"
    )

    if regime == "CHOPPY":
        logger.info("[SKIP-REGIME] Market sedang CHOPPY (Sideways). Bot menahan diri.")
        return state

    # -- AGENT DEEPSEEK (UPDATE MAKRO BIAS) ---------------------
    global LAST_DEEPSEEK_TIME, CURRENT_MACRO_BIAS
    now_ts = time.time()
    # Panggil DeepSeek setiap 2 jam (7200 detik)
    if now_ts - LAST_DEEPSEEK_TIME > 7200:
        logger.info("[DEEPSEEK] Menghubungi DeepSeek untuk analisis Makro...")
        ds_context = f"Harga XAUUSD {harga:.2f}, ATR {atr:.2f}, Regime {regime}. Tolong cek sentimen saat ini."
        CURRENT_MACRO_BIAS = get_macro_bias(ds_context)
        LAST_DEEPSEEK_TIME = now_ts
        logger.info(f"[DEEPSEEK] Bias Update: {CURRENT_MACRO_BIAS}")
    
    # Rangkum Konteks untuk Ingatan Hermes
    konteks_pasar = f"Harga: {harga:.2f}, ATR: {atr:.2f}, Regime: {regime}"


    # -- Pra-Kondisi: Tidak Ada Posisi Terbuka ------------------
    if ada_posisi_terbuka():
        logger.info("[INFO] Ada posisi terbuka, skip entry baru.")
        return state

    # -- Pra-Kondisi: Cek Limit Trade Hari Ini ------------------
    if state["trade_hari_ini"] >= cfg.MAX_TRADE_PER_HARI:
        logger.info(
            f"[STOP] Max trade hari ini ({cfg.MAX_TRADE_PER_HARI}) sudah tercapai."
        )
        return state

    # -- Pra-Kondisi: Cek Pause Setelah Loss Beruntun -----------
    if state["loss_beruntun"] >= cfg.MAX_LOSS_BERUNTUN:
        sisa_pause = state.get("resume_time", 0) - time.time()
        if sisa_pause > 0:
            logger.info(
                f"[PAUSE] Loss beruntun {state['loss_beruntun']}x. "
                f"Pause {int(sisa_pause/60)} menit lagi..."
            )
            return state
        else:
            state["loss_beruntun"] = 0
            logger.info("[RESUME] Pause selesai. Kembali aktif.")

    # ============================================================
    # CEK SINYAL BUY (XGBOOST ML)
    # ============================================================
    ai_buy_ok = prob_buy >= cfg.ML_CONFIDENCE_THRESHOLD

    if ai_buy_ok:
        # -- MTFA Layer 3: Cek Trigger M5 untuk BUY --------------
        trigger_buy_m5, info_m5_buy = cek_trigger_m5(df_m5, "BUY") if cfg.MTFA_M5_AKTIF else (True, "M5 off")
        logger.info(f"[M5]  Trigger BUY: {ok_str(trigger_buy_m5)} | {info_m5_buy}")

        if not trigger_buy_m5:
            logger.info("[SKIP-M5] Candle M5 belum bullish, tunggu konfirmasi M5 dulu.")
        else:
            logger.info(">>> SINYAL BUY - Semua konfluensi terpenuhi! (H1+M15+M5) <<<")

            sl = tick.ask - (atr * cfg.ATR_SL_MULTIPLIER)
            tp_atr = tick.ask + (atr * cfg.ATR_TP_MULTIPLIER)

            tp_candidates = [bb["middle"], tp_atr]
            if pivot and cfg.GUNAKAN_PP_SEBAGAI_TP:
                tp_candidates.append(pivot["pp"])
            tp_valid = [t for t in tp_candidates if t > tick.ask]
            tp = min(tp_valid) if tp_valid else tp_atr

            rr = (tp - tick.ask) / (tick.ask - sl) if (tick.ask - sl) > 0 else 0
            logger.info(
                f"Entry BUY | Ask: {tick.ask:.2f} | SL: {sl:.2f} | "
                f"TP: {tp:.2f} | RR: 1:{rr:.2f}"
            )

            # -- AGENT HERMES (Final Approval) -----------------------
            ingatan = retrieve_relevant_memory(konteks_pasar)
            konteks_full = f"{konteks_pasar} | Memory: {ingatan}"
            xgb_sig = {"direction": "BUY", "confidence": prob_buy}
            
            logger.info("[HERMES] Meminta persetujuan eksekusi dari Hermes...")
            keputusan = evaluate_execution(xgb_sig, CURRENT_MACRO_BIAS, konteks_full)
            logger.info(f"[HERMES] Keputusan: {keputusan['action']} | Alasan: {keputusan['reason']}")

            if keputusan["action"] == "EXECUTE":
                berhasil = kirim_order(mt5.ORDER_TYPE_BUY, filling_mode, sl, tp, prob_buy, keputusan.get("lot_multiplier", 1.0))
                if berhasil:
                    state["trade_hari_ini"] += 1
                    state["loss_beruntun"]   = 0
            else:
                logger.warning(f"[HOLD] Hermes membatalkan eksekusi BUY XGBoost. Alasan: {keputusan['reason']}")
            return state

    # ============================================================
    # CEK SINYAL SELL (XGBOOST ML)
    # ============================================================
    ai_sell_ok = prob_sell >= cfg.ML_CONFIDENCE_THRESHOLD

    if ai_sell_ok:
        # -- MTFA Layer 3: Cek Trigger M5 untuk SELL -------------
        trigger_sell_m5, info_m5_sell = cek_trigger_m5(df_m5, "SELL") if cfg.MTFA_M5_AKTIF else (True, "M5 off")
        logger.info(f"[M5]  Trigger SELL: {ok_str(trigger_sell_m5)} | {info_m5_sell}")

        if not trigger_sell_m5:
            logger.info("[SKIP-M5] Candle M5 belum bearish, tunggu konfirmasi M5 dulu.")
        else:
            logger.info(">>> SINYAL SELL - Semua konfluensi terpenuhi! (H1+M15+M5) <<<")

            sl = tick.bid + (atr * cfg.ATR_SL_MULTIPLIER)
            tp_atr = tick.bid - (atr * cfg.ATR_TP_MULTIPLIER)

            tp_candidates = [bb["middle"], tp_atr]
            if pivot and cfg.GUNAKAN_PP_SEBAGAI_TP:
                tp_candidates.append(pivot["pp"])
            tp_valid = [t for t in tp_candidates if t < tick.bid]
            tp = max(tp_valid) if tp_valid else tp_atr

            rr = (tick.bid - tp) / (sl - tick.bid) if (sl - tick.bid) > 0 else 0
            logger.info(
                f"Entry SELL | Bid: {tick.bid:.2f} | SL: {sl:.2f} | "
                f"TP: {tp:.2f} | RR: 1:{rr:.2f}"
            )

            # -- AGENT HERMES (Final Approval) -----------------------
            ingatan = retrieve_relevant_memory(konteks_pasar)
            konteks_full = f"{konteks_pasar} | Memory: {ingatan}"
            xgb_sig = {"direction": "SELL", "confidence": prob_sell}
            
            logger.info("[HERMES] Meminta persetujuan eksekusi dari Hermes...")
            keputusan = evaluate_execution(xgb_sig, CURRENT_MACRO_BIAS, konteks_full)
            logger.info(f"[HERMES] Keputusan: {keputusan['action']} | Alasan: {keputusan['reason']}")

            if keputusan["action"] == "EXECUTE":
                berhasil = kirim_order(mt5.ORDER_TYPE_SELL, filling_mode, sl, tp, prob_sell, keputusan.get("lot_multiplier", 1.0))
                if berhasil:
                    state["trade_hari_ini"] += 1
                    state["loss_beruntun"]   = 0
            else:
                logger.warning(f"[HOLD] Hermes membatalkan eksekusi SELL XGBoost. Alasan: {keputusan['reason']}")
            return state

    logger.info("[~] Tidak ada sinyal valid. Menunggu candle berikutnya...")
    return state


# ===============================================================
# MONITOR POSISI TERTUTUP (Update Loss Beruntun)
# ===============================================================
def update_loss_beruntun(state):
    """Cek histori deal terbaru untuk update tracking loss beruntun."""
    history = mt5.history_deals_get(
        datetime.now() - timedelta(hours=24),
        datetime.now(),
    )
    if history is None:
        return state

    deals_bot = [
        d for d in history
        if d.magic == cfg.MAGIC_NUMBER and d.entry == mt5.DEAL_ENTRY_OUT
    ]

    if not deals_bot:
        return state

    last_deal = max(deals_bot, key=lambda d: d.time)
    if last_deal.profit < 0:
        if state.get("last_deal_ticket") != last_deal.ticket:
            state["loss_beruntun"] += 1
            state["last_deal_ticket"] = last_deal.ticket
            save_trade_memory(last_deal.ticket, "TRADE", "LOSS", last_deal.profit, "Kondisi market pasca-loss (RAG update)")
            logger.warning(
                f"[WARN] Loss terdeteksi! Loss beruntun: {state['loss_beruntun']}x"
            )
            if state["loss_beruntun"] >= cfg.MAX_LOSS_BERUNTUN:
                state["resume_time"] = time.time() + (cfg.PAUSE_SETELAH_LOSS * 60)
                logger.warning(
                    f"[PAUSE] Loss beruntun {state['loss_beruntun']}x! "
                    f"Bot pause {cfg.PAUSE_SETELAH_LOSS} menit."
                )
    else:
        if state.get("last_deal_ticket") != last_deal.ticket:
            state["loss_beruntun"] = 0
            state["last_deal_ticket"] = last_deal.ticket
            save_trade_memory(last_deal.ticket, "TRADE", "WIN", last_deal.profit, "Kondisi market pasca-win (RAG update)")

    return state


# ===============================================================
# NOTION INTEGRATION
# ===============================================================
def kirim_laporan_ke_notion(teks_laporan):
    """Kirim teks laporan harian ke Notion Page sebagai Code Block."""
    if not getattr(cfg, "ENABLE_NOTION_LOG", False):
        return

    try:
        from notion_client import Client
    except ImportError:
        logger.error("[NOTION] Library notion-client belum di-install. Jalankan: pip install notion-client")
        return

    # Notion punya limit 2000 karakter per rich_text block
    if len(teks_laporan) > 2000:
        teks_laporan = teks_laporan[:1950] + "\n\n[TERPOTONG KARENA LIMIT NOTION]"

    try:
        notion = Client(auth=cfg.NOTION_API_KEY)
        notion.blocks.children.append(
            block_id=cfg.NOTION_PAGE_ID,
            children=[
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": teks_laporan
                                }
                            }
                        ],
                        "language": "plain text"
                    }
                }
            ]
        )
        logger.info("[NOTION] Laporan Harian berhasil dikirim ke Notion!")
    except Exception as e:
        logger.error(f"[NOTION] Gagal mengirim ke Notion: {e}")

# ===============================================================
# LAPORAN HARIAN
# ===============================================================
def buat_laporan_harian(tanggal, total_trade_bot):
    """
    Buat laporan harian berisi statistik trade hari ini.
    Dipanggil saat sesi Asia selesai (jam 14:30 WIB).
    Laporan disimpan ke folder 'laporan/' dan juga di-log.
    """
    import os

    # Ambil histori deal hari ini dari MT5
    awal_hari = datetime.combine(tanggal, datetime.min.time())
    akhir_hari = datetime.combine(tanggal, datetime.max.time())

    history = mt5.history_deals_get(awal_hari, akhir_hari)
    account = mt5.account_info()

    deals_bot = []
    if history:
        deals_bot = [
            d for d in history
            if d.magic == cfg.MAGIC_NUMBER and d.entry == mt5.DEAL_ENTRY_OUT
        ]

    # Hitung statistik
    total   = len(deals_bot)
    wins    = [d for d in deals_bot if d.profit > 0]
    losses  = [d for d in deals_bot if d.profit <= 0]
    total_profit = sum(d.profit for d in deals_bot)
    win_rate = (len(wins) / total * 100) if total > 0 else 0
    best_trade  = max((d.profit for d in deals_bot), default=0)
    worst_trade = min((d.profit for d in deals_bot), default=0)

    # Format laporan
    garis  = "=" * 55
    garis2 = "-" * 55
    laporan = [
        garis,
        f"  LAPORAN HARIAN SCALPING BOT - {tanggal.strftime('%d %B %Y')}  ",
        garis,
        f"  Broker  : {account.company if account else 'N/A'}",
        f"  Akun    : {account.login if account else 'N/A'}",
        f"  Symbol  : {cfg.SYMBOL}",
        f"  Balance : ${account.balance:.2f}" if account else "  Balance : N/A",
        f"  Equity  : ${account.equity:.2f}" if account else "  Equity  : N/A",
        garis2,
        f"  RINGKASAN TRADING HARI INI",
        garis2,
        f"  Total Trade      : {total} trade",
        f"  Menang (Win)     : {len(wins)} trade",
        f"  Kalah  (Loss)    : {len(losses)} trade",
        f"  Win Rate         : {win_rate:.1f}%",
        garis2,
        f"  PROFIT / LOSS",
        garis2,
        f"  Total P&L        : ${total_profit:+.2f}",
        f"  Trade Terbaik    : ${best_trade:+.2f}",
        f"  Trade Terburuk   : ${worst_trade:+.2f}",
        garis2,
        f"  DETAIL TRADE",
        garis2,
    ]

    if deals_bot:
        for i, d in enumerate(deals_bot, 1):
            tipe   = "BUY " if d.type == mt5.DEAL_TYPE_BUY else "SELL"
            waktu  = datetime.fromtimestamp(d.time).strftime("%H:%M")
            status = "WIN " if d.profit > 0 else "LOSS"
            laporan.append(
                f"  #{i:02d} [{waktu}] {tipe} | {status} | P&L: ${d.profit:+.2f} | Vol: {d.volume}"
            )
    else:
        laporan.append("  Tidak ada trade hari ini.")
        if total_trade_bot == 0:
            laporan.append("  Bot aktif tapi tidak ada sinyal yang memenuhi syarat.")

    laporan += [
        garis2,
        f"  Sesi Asia : 07:00 - 14:30 WIB",
        f"  Laporan dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        garis,
    ]

    teks_laporan = "\n".join(laporan)

    # Log laporan ke terminal
    logger.info("\n" + teks_laporan)
    
    # Kirim ke Notion
    kirim_laporan_ke_notion(teks_laporan)
    
    # Bersihkan file log mentah lokal (trading_scalping.log) dengan aman di Windows
    try:
        import logging
        for handler in logging.root.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.stream.close()  # Lepas penguncian (lock) dari handler
                with open(handler.baseFilename, "w"):
                    pass                # Kosongkan file
                handler.stream = open(handler.baseFilename, "a", encoding="utf-8") # Buka lagi
        logger.info("[MAINTENANCE] File log lokal (trading_scalping.log) berhasil dikosongkan.")
    except Exception as e:
        logger.error(f"[MAINTENANCE] Gagal mengosongkan log: {e}")

    return "Notion"


# ===============================================================
# MAIN LOOP
# ===============================================================
def main():
    setup_logging()
    init_mt5()
    filling_mode = detect_filling_mode()

    state = {
        "trade_hari_ini":    0,
        "loss_beruntun":     0,
        "resume_time":       0,
        "last_deal_ticket":  None,
        "hari_ini":          datetime.now().date(),
        "laporan_dibuat":    False,   # Flag agar laporan tidak dibuat dobel
    }

    logger.info("Bot mulai berjalan. Tekan Ctrl+C untuk stop.")

    try:
        while True:
            # -- Reset counter jika hari baru --------------------
            hari_sekarang = datetime.now().date()
            if hari_sekarang != state["hari_ini"]:
                state["trade_hari_ini"] = 0
                state["hari_ini"]       = hari_sekarang
                state["laporan_dibuat"] = False
                logger.info("[DATE] Hari baru - counter trade direset.")

            # -- Cek Sesi Asia -----------------------------------
            aktif, info_waktu = adalah_sesi_asia()

            if not aktif:
                # Buat laporan harian saat sesi baru saja selesai
                if not state["laporan_dibuat"]:
                    logger.info("[LAPORAN] Sesi Asia selesai. Membuat laporan harian...")
                    buat_laporan_harian(state["hari_ini"], state["trade_hari_ini"])
                    state["laporan_dibuat"] = True

                menit = menit_ke_sesi_asia()
                logger.info(
                    f"[SLEEP] Di luar sesi Asia ({info_waktu}). "
                    f"Hibernasi {menit} menit sampai 07:00 WIB."
                )
                time.sleep(cfg.SLEEP_LUAR_SESI)
                continue

            logger.info(
                f"[AKTIF] Sesi Asia ({info_waktu}) | "
                f"Trade hari ini: {state['trade_hari_ini']}/{cfg.MAX_TRADE_PER_HARI}"
            )

            # -- Update Loss Beruntun ----------------------------
            state = update_loss_beruntun(state)

            # -- Guard: Jangan entry di 15 menit terakhir sesi ---
            aman, pesan_waktu = is_waktu_aman_entry()
            if not aman:
                logger.info(pesan_waktu)
                time.sleep(cfg.SLEEP_CANDLE)
                continue

            # -- Analisis & Entry --------------------------------
            state = analisis_dan_entry(filling_mode, state)

            # -- Tunggu interval berikutnya ----------------------
            time.sleep(cfg.SLEEP_CANDLE)

    except KeyboardInterrupt:
        # Buat laporan saat bot di-stop manual
        logger.info("\n[STOP] Bot dihentikan oleh user (Ctrl+C).")
        logger.info("[LAPORAN] Membuat laporan sesi terakhir...")
        buat_laporan_harian(state["hari_ini"], state["trade_hari_ini"])
    except Exception as e:
        logger.exception(f"[ERROR] Error tidak terduga: {e}")
    finally:
        shutdown_mt5()


# ===============================================================
if __name__ == "__main__":
    main()
