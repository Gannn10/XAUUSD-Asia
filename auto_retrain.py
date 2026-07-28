import os
import shutil
import pickle
import logging
import MetaTrader5 as mt5
import pandas as pd
import polars as pl
import xgboost as xgb
from datetime import datetime
import sys

import config_scalping as cfg
from train_ml_v3 import MLTrainerV3

logger = logging.getLogger("AutoRetrain")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")

class RetrainerWithHoldOut(MLTrainerV3):
    def __init__(self, holdout_bars=1000):
        super().__init__()
        self.holdout_bars = holdout_bars

    def fetch_training_data(self, n_bars: int = 50000) -> pl.DataFrame:
        """Override untuk menyisakan data hold-out yang belum pernah dilihat"""
        logger.info(f"Mengambil {n_bars} data training (Melewati {self.holdout_bars} candle terakhir sebagai Hold-Out)...")
        # Posisi dimulai dari holdout_bars, jadi 1000 candle terakhir tidak ikut terambil
        rates = mt5.copy_rates_from_pos(cfg.SYMBOL, cfg.M5_TIMEFRAME, self.holdout_bars, n_bars)
        if rates is None or len(rates) == 0:
            raise ValueError("Gagal mengambil data M5.")
            
        df_pd = pd.DataFrame(rates)
        df_pd['time'] = pd.to_datetime(df_pd['time'], unit='s')
        return pl.from_pandas(df_pd)
        
    def fetch_h1_data(self, n_bars: int = 5000) -> pl.DataFrame:
        """Override untuk H1 agar seimbang dengan M5 holdout"""
        # 1000 candle M5 kira-kira setara dengan 83 candle H1
        holdout_h1 = int(self.holdout_bars / 12) + 1
        rates = mt5.copy_rates_from_pos(cfg.SYMBOL, mt5.TIMEFRAME_H1, holdout_h1, n_bars)
        df_pd = pd.DataFrame(rates)
        df_pd['time'] = pd.to_datetime(df_pd['time'], unit='s')
        return pl.from_pandas(df_pd)

def get_holdout_data(holdout_bars=1000):
    """Ambil data yang benar-benar fresh (belum dilihat model saat training)."""
    rates_m5 = mt5.copy_rates_from_pos(cfg.SYMBOL, cfg.M5_TIMEFRAME, 0, holdout_bars)
    df_pd = pd.DataFrame(rates_m5)
    df_pd['time'] = pd.to_datetime(df_pd['time'], unit='s')
    df_m5 = pl.from_pandas(df_pd)
    
    rates_h1 = mt5.copy_rates_from_pos(cfg.SYMBOL, mt5.TIMEFRAME_H1, 0, 200) # Cukup 200 untuk H1
    df_pd_h1 = pd.DataFrame(rates_h1)
    df_pd_h1['time'] = pd.to_datetime(df_pd_h1['time'], unit='s')
    df_h1 = pl.from_pandas(df_pd_h1)
    
    return df_m5, df_h1

def evaluate_on_holdout(model_path, df_m5, df_h1, trainer_instance):
    """Jalankan model pada data Hold-Out untuk mencari True Accuracy."""
    try:
        with open(model_path, "rb") as f:
            model_data = pickle.load(f)
            model = model_data["xgb_model"]
            features = model_data["feature_names"]
            
        # Proses Feature Engineering pada data Hold Out
        df_features = trainer_instance.engineer_features(df_m5, df_h1)
        df_labeled = trainer_instance.label_data(df_features)
        
        # Filter yang sudah punya target
        df_eval = df_labeled.filter((pl.col("target").is_not_null()) & (pl.col("target") >= 0))
        
        if len(df_eval) == 0:
            return 0.0
            
        X = df_eval.select(features).to_numpy()
        y_true = df_eval["target"].to_numpy()
        
        # Prediksi
        if isinstance(model, xgb.Booster):
            dmatrix = xgb.DMatrix(X, feature_names=features)
            y_pred_prob = model.predict(dmatrix)
            y_pred = (y_pred_prob > 0.5).astype(int)
        else:
            y_pred = model.predict(X)
            
        accuracy = (y_pred == y_true).mean()
        return float(accuracy)
    except Exception as e:
        logger.error(f"Gagal evaluasi model {model_path}: {e}")
        return 0.0

def main():
    logger.info("Memulai Proses Dynamic Auto-Retraining...")
    
    holdout_bars = 1000 # Menyisakan ~3 hari terakhir market untuk A/B testing
    trainer = RetrainerWithHoldOut(holdout_bars=holdout_bars)
    
    # 1. Mulai Training Model Baru dengan HoldOut
    new_model_name = "xgboost_model_v3_new.pkl"
    # Ganti output default name secara runtime
    original_save = trainer.save_model
    def mock_save():
        original_save(output_name=new_model_name)
    trainer.save_model = mock_save
    
    logger.info("Tahap 1: Latihan Model Baru...")
    try:
        trainer.run_full_pipeline()
    except Exception as e:
        logger.error(f"Training gagal: {e}. Retraining dibatalkan.")
        sys.exit(1)
    
    # 2. Tarik Data Hold-Out (True Unseen Data)
    logger.info("Tahap 2: Menarik Data Hold-Out (Masa Depan) untuk Evaluasi...")
    df_m5_holdout, df_h1_holdout = get_holdout_data(holdout_bars)
    
    old_model_path = os.path.join(trainer.output_dir, "xgboost_model_v3.pkl")
    new_model_path = os.path.join(trainer.output_dir, new_model_name)
    
    # 3. A/B Testing
    logger.info("Tahap 3: Memulai A/B Testing (Old vs New)...")
    acc_old = 0.0
    if os.path.exists(old_model_path):
        acc_old = evaluate_on_holdout(old_model_path, df_m5_holdout, df_h1_holdout, trainer)
    
    acc_new = evaluate_on_holdout(new_model_path, df_m5_holdout, df_h1_holdout, trainer)
    
    logger.info(f"[A/B Test Result] Akurasi Hold-Out Model LAMA: {acc_old*100:.2f}%")
    logger.info(f"[A/B Test Result] Akurasi Hold-Out Model BARU: {acc_new*100:.2f}%")
    
    # 4. Keputusan
    if acc_new > acc_old:
        logger.info("🔥 KEPUTUSAN: Model Baru lebih pintar! Melakukan pergantian (Update)...")
        if os.path.exists(old_model_path):
            backup_path = os.path.join(trainer.output_dir, f"xgboost_model_v3_backup_{int(datetime.now().timestamp())}.pkl")
            shutil.move(old_model_path, backup_path)
            logger.info(f"Model lama dibackup ke {backup_path}")
            
        shutil.move(new_model_path, old_model_path)
        
        # Pindahkan juga metadata
        old_meta = old_model_path.replace(".pkl", "_metadata.json")
        new_meta = new_model_path.replace(".pkl", "_metadata.json")
        if os.path.exists(new_meta):
            shutil.move(new_meta, old_meta)
            
        logger.info("Update selesai! Model baru siap digunakan untuk Senin pagi.")
    else:
        logger.info("🛡️ KEPUTUSAN: Model Baru OVERFITTING/LEBIH BODOH. Pembaruan dibatalkan.")
        if os.path.exists(new_model_path):
            os.remove(new_model_path)
            new_meta = new_model_path.replace(".pkl", "_metadata.json")
            if os.path.exists(new_meta):
                os.remove(new_meta)
        logger.info("Model lama tetap dipertahankan.")

if __name__ == "__main__":
    main()
