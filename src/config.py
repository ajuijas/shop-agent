from dotenv import load_dotenv
from dataclasses import dataclass
import os


# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """Application configuration"""
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    FAISS_INDEX_PATH: str = "index/products.index"
    PRODUCT_ID_MAP_PATH: str = "index/product_ids.json"
    TOP_K_RESULTS: int = 50

config = Config()