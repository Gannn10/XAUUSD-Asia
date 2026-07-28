# 🤖 XAU/USD Asia Scalping Bot (Agentic AI Edition)

![Version](https://img.shields.io/badge/version-3.0.0--agentic-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen)
![Status](https://img.shields.io/badge/status-active-success)

Sebuah bot scalping otomatis (EA) kelas institusional untuk MetaTrader 5 (MT5), dirancang secara spesifik untuk mengeksploitasi pergerakan *mean-reversion* / *ranging* XAU/USD (Gold) pada sesi Asia (07:00 – 14:30 WIB).

Bot ini merupakan evolusi dari arsitektur *Rule-Based* klasik menjadi **Sistem Bertenaga AI (Agentic AI)**.

## ✨ Fitur Utama

1. **XGBoost Machine Learning Engine**: Menggantikan indikator teknikal murni dengan probabilitas ML yang dilatih menggunakan *Triple Barrier Method*. Bot bisa memprediksi ke arah mana market akan bergerak berdasarkan pola historis M5 dan H1.
2. **Smart Money Concept (SMC) dengan Polars**: Ekstraksi fitur secepat kilat menggunakan *Polars*. Mendeteksi *Fair Value Gaps* (FVG), *Order Blocks* (OB), dan *Liquidity Sweeps* untuk melihat jejak rekam aliran dana institusi.
3. **HMM Regime Detector (Hidden Markov Model)**: Detektor "cuaca" pasar yang pintar. Jika HMM mendeteksi pasar sedang *Choppy* atau dipenuhi volatilitas tak beraturan, bot akan melakukan hibernasi (pause) secara otomatis untuk melindungi saldo Anda.
4. **Agentic Execution (Hermes & DeepSeek)**: Keputusan akhir tidak hanya diserahkan pada hitungan matematis, tapi dievaluasi oleh agen AI (LLM) secara *real-time*. DeepSeek bertugas merangkum *macro bias*, sedangkan Hermes (via OpenRouter) menyetujui, membatalkan (HOLD), atau menyesuaikan *Lot Size* berdasarkan konteks market dan ingatan (*Memory RAG*).
5. **Smart Breakeven & Kelly Position Scaler**: Manajemen risiko canggih yang secara otomatis memindahkan *Stop Loss* ke posisi *Break-Even* (BEP) jika sudah *running profit* 15 pips. Ukuran Lot disesuaikan dinamis sesuai *confidence level* tebakan AI (mirip dengan metode *Kelly Criterion*).

## 📂 Struktur Repositori

- `scalping_bot.py`: Main engine / entry point untuk Bot Sesi Asia.
- `config_scalping.py`: File konfigurasi (Lot size, Threshold ML, Jam operasional).
- `feature_eng.py` & `smc_polars.py`: Otak *feature engineering* data historis menggunakan Polars.
- `regime_detector.py`: Filter entry berdasar *Hidden Markov Model*.
- `agent_hermes.py` & `agent_deepseek.py`: Layer Agen LLM yang mengambil keputusan akhir.
- `memory_rag.py`: Modul memori (Vector Database) untuk pengalaman *Agentic* berlanjut.
- `train_ml_v3.py` & `triple_barrier_labeling.py`: Script pipeline pelatihan model XGBoost.
- `backtests/`: Folder penyimpanan model `.pkl` (seperti `xgboost_model_v3.pkl`).
- `LondonNewyork/`: Modul bot terpisah untuk menguasai sesi volatilitas tinggi (London & NY).

## 🚀 Instalasi & Persiapan

1. Pastikan Anda memiliki Python 3.10 atau lebih baru dan Terminal MT5 yang sudah login ke broker Anda (Disarankan: akun Raw Spread/Zero Spread exness).
2. Clone repository ini:
   ```bash
   git clone https://github.com/Gannn10/XAUUSD-Asia.git
   cd XAUUSD-Asia
   ```
3. Install dependensi (termasuk *Machine Learning libs*):
   ```bash
   pip install -r requirements.txt
   pip install polars hmmlearn
   ```
4. Masukkan **API Keys** Anda (JANGAN upload/commit API key Anda ke GitHub!):
   - Buka file `config_scalping.py` secara lokal.
   - Isi `NOTION_API_KEY` (jika mengaktifkan notifikasi Notion).
   - Isi `OPENROUTER_API_KEY` untuk memberi kehidupan pada agen eksekusi *Hermes*.

## 🎯 Cara Menjalankan

Buka terminal, pastikan MetaTrader 5 sedang terbuka, lalu jalankan:

```bash
python scalping_bot.py
```

Pantau log di terminal atau baca file `trading_scalping.log` untuk melihat percakapan log internal antar-Agen.

## ⚠️ Disclaimer

Trading komoditas dengan leverage tinggi (seperti XAU/USD) memiliki risiko tingkat tinggi. Bot ini dirancang sebagai eksperimen *Agentic AI Algo Trading*. Pastikan Anda menjalankannya secara menyeluruh di akun DEMO terlebih dahulu sebelum beralih menggunakan uang nyata (Real Account).
