import json
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

DATA_DIR = Path(__file__).resolve().parent / "data"


def initialize_data_directory():
    """
    Clears the existing data directory and recreates it.
    """
    if DATA_DIR.exists():
        try:
            shutil.rmtree(DATA_DIR)
        except Exception as e:
            print(f"[DataManager] Warning: Could not clear data directory: {e}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[DataManager] Data directory '{DATA_DIR}' initialized.")


def save_json(filename: str, data: Any):
    """
    Saves data to a JSON file. Creates directory if missing.
    """
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    file_path = DATA_DIR / filename

    def serializable(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return obj

    try:
        if isinstance(data, list):
            serialized_data = [serializable(item) for item in data]
        else:
            serialized_data = serializable(data)

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(serialized_data, f, indent=4, default=str)

    except Exception as e:
        print(f"[DataManager] Error saving {filename}: {e}")