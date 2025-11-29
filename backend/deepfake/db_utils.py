# This file will handle MongoDB integration for deepfake results.
from pymongo import MongoClient
from typing import Dict, Any

client = MongoClient("mongodb://localhost:27017/")  # Update with your MongoDB URI

db = client["mumbai_hacks"]
collection = db["deepfake_results"]

def save_result(result: Dict[str, Any]):
    collection.insert_one(result)

def get_results():
    return list(collection.find())
