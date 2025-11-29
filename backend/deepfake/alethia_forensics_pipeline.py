import os
import logging
import cv2
import torch
import numpy as np
from typing import Optional, Tuple, List
from PIL import Image
from io import BytesIO
import base64
from .model.config import load_config
from .model.pred_func import load_genconvit

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
GENCON_MODEL = None
MODEL_LOADED = False
MODEL_ERROR = None

def check_weights_available():
    """Check if weights folder and required weight files exist"""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    weight_dir = os.path.join(root_dir, 'weights')
    ed_path = os.path.join(weight_dir, 'genconvit_ed_inference.pth')
    vae_path = os.path.join(weight_dir, 'genconvit_vae_inference.pth')
    
    if not os.path.exists(weight_dir):
        return False, "Weights folder not found"
    if not os.path.exists(ed_path):
        return False, f"ED weight file not found: {ed_path}"
    if not os.path.exists(vae_path):
        return False, f"VAE weight file not found: {vae_path}"
    return True, None

def get_local_model():
    """Get the local model, or None if weights are not available"""
    global GENCON_MODEL, MODEL_LOADED, MODEL_ERROR
    
    # Check if weights are available first
    weights_available, error_msg = check_weights_available()
    if not weights_available:
        if not MODEL_LOADED:  # Only log once
            logging.warning(f"Deepfake model weights not available: {error_msg}")
            logging.warning("Deepfake detection will be disabled. Add weights folder to enable.")
            MODEL_ERROR = error_msg
            MODEL_LOADED = True
        return None
    
    if GENCON_MODEL is None:
        logging.info("Loading GenConViT model...")
        try:
            config = load_config()
            ed_weight = 'genconvit_ed_inference'
            vae_weight = 'genconvit_vae_inference'
            # Pass None for net to use BOTH ED and VAE models (hybrid approach)
            GENCON_MODEL = load_genconvit(config, None, ed_weight, vae_weight, fp16=False)
            GENCON_MODEL.to(DEVICE)
            GENCON_MODEL.eval()
            logging.info("GenConViT model loaded successfully (ED + VAE hybrid).")
            MODEL_LOADED = True
            MODEL_ERROR = None
        except FileNotFoundError as e:
            logging.error(f"Failed to load GenConViT weights: {e}")
            MODEL_ERROR = str(e)
            MODEL_LOADED = True
            return None
        except Exception as e:
            # If model was created but loading had issues, try to use it anyway
            if GENCON_MODEL is not None:
                try:
                    GENCON_MODEL.to(DEVICE)
                    GENCON_MODEL.eval()
                    logging.warning(f"GenConViT model loaded with warnings (partial weights may affect accuracy): {e}")
                    logging.info("Model will be used but may have reduced accuracy due to weight mismatches.")
                    MODEL_LOADED = True
                    MODEL_ERROR = None
                    return GENCON_MODEL
                except Exception as e2:
                    logging.error(f"Failed to finalize model after partial load: {e2}")
            else:
                logging.error(f"Failed to create GenConViT model: {e}")
            MODEL_ERROR = str(e)
            MODEL_LOADED = True
            return None
    return GENCON_MODEL

def is_model_available():
    """Check if model is available for use"""
    model = get_local_model()
    return model is not None

def extract_frames(video_path: str, num_frames: int = 30) -> List[np.ndarray]:
    frames = []
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error("Error: Could not open video file.")
        return []
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames < 1:
        logging.error("Error: Video file has no frames.")
        return []
    if total_frames < num_frames:
        indices = np.arange(total_frames).astype(int)
    else:
        indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
    cap.release()
    return frames

def convert_frame_to_base64(frame: np.ndarray) -> str:
    try:
        pil_img = Image.fromarray(frame)
        buffer = BytesIO()
        pil_img.save(buffer, format="JPEG")
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        logging.error(f"Failed to convert frame to Base64: {e}")
        return None
