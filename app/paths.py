from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "app" / "data"
AUDIO_DIR = DATA_DIR / "audio_records"
DB_PATH = DATA_DIR / "tutor.db"
