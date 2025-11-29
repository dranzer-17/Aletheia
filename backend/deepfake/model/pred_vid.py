import torch
import numpy as np

def max_prediction_value(y_pred):
    """
    Finds the index and value of the maximum prediction value.
    Handles both single model and hybrid (ED+VAE) concatenated outputs.
    
    IMPORTANT: For this model, the interpretation is inverted:
    - mean_val[0] close to 0 = REAL video
    - mean_val[0] close to 1 = FAKE video
    """
    # For hybrid model, y_pred has shape [2*num_frames, 2] after concatenation
    # We need to average across all predictions
    mean_val = torch.mean(y_pred, dim=0)
    
    real_score = mean_val[0].item()
    fake_score = mean_val[1].item()
    
    # Log mean values for debugging
    print(f"[Deepfake Debug] Mean scores: real={real_score:.4f}, fake={fake_score:.4f}")
    
    # Inverted logic: if real_score is LOW (close to 0), it's REAL
    # if real_score is HIGH (close to 1), it's FAKE
    if real_score < 0.5:
        pred_class = 1  # REAL
        confidence = 1.0 - real_score  # Confidence in being REAL
    else:
        pred_class = 0  # FAKE
        confidence = real_score  # Confidence in being FAKE
    
    # Also return both mean values for thresholding
    return (pred_class, confidence, real_score, fake_score)

def pred_vid(face_tensor, model):
    with torch.no_grad():
        y = model(face_tensor)  # Use the full model forward pass (ED + VAE hybrid)
        return max_prediction_value(torch.sigmoid(y.squeeze()))
