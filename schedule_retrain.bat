@echo off
echo ==========================================
echo AUTO-RETRAIN XGBOOST BOT SCALPING
echo ==========================================
echo Memulai proses pelatihan ulang berbasis A/B Testing...
echo Peringatan: Jangan tutup jendela ini!
echo.
cd /d "d:\Bot XAUUSD\scalping"
python auto_retrain.py
echo.
echo Proses selesai.
pause
