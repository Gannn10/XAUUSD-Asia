import os
import chromadb
from chromadb.config import Settings
import logging
from datetime import datetime

logger = logging.getLogger("Memory_RAG")

# Inisialisasi ChromaDB lokal
DB_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)

try:
    client = chromadb.PersistentClient(path=DB_PATH, settings=Settings(allow_reset=True))
    collection = client.get_or_create_collection(name="asia_session_memory")
except Exception as e:
    logger.error(f"Gagal inisialisasi ChromaDB: {e}")
    collection = None

def save_trade_memory(ticket: int, action: str, result: str, profit: float, context: str):
    """
    Menyimpan hasil trade ke dalam vektor memori.
    action: "BUY" atau "SELL"
    result: "WIN" atau "LOSS"
    """
    if collection is None:
        return

    doc_id = f"trade_{ticket}_{int(datetime.now().timestamp())}"
    text_content = f"Trade {action} resulted in {result} with profit {profit:.2f}. Market context was: {context}"
    
    metadata = {
        "action": action,
        "result": result,
        "profit": profit,
        "timestamp": datetime.now().timestamp()
    }

    try:
        collection.add(
            documents=[text_content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.info(f"[MEMORY] Trade {ticket} disimpan ke ingatan jangka panjang.")
    except Exception as e:
        logger.error(f"[MEMORY] Gagal menyimpan trade: {e}")

def retrieve_relevant_memory(current_context: str, n_results=3) -> str:
    """
    Mencari memori trading masa lalu yang mirip dengan kondisi saat ini.
    """
    if collection is None:
        return "Memory DB is not available."

    try:
        # Cek jumlah data
        if collection.count() == 0:
            return "Belum ada memori masa lalu."

        # Ambil max sesuai jumlah isi DB
        n = min(n_results, collection.count())
        
        results = collection.query(
            query_texts=[current_context],
            n_results=n
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "Tidak ada memori yang relevan."
            
        memories = results['documents'][0]
        return " | ".join(memories)
    except Exception as e:
        logger.error(f"[MEMORY] Gagal menarik memori: {e}")
        return "Error saat menarik memori."

if __name__ == "__main__":
    # Test lokal
    save_trade_memory(12345, "BUY", "LOSS", -15.5, "Harga ranging di 2310, volatilitas rendah.")
    save_trade_memory(12346, "SELL", "WIN", 20.0, "Harga rejection dari resistance 2315.")
    
    print("Mencoba mengingat kondisi ranging:")
    print(retrieve_relevant_memory("Harga sideways di area 2310"))
