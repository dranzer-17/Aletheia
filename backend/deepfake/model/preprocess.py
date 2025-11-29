import torch
from ..dataset.loader import normalize_data

device = "cuda" if torch.cuda.is_available() else "cpu"

def preprocess_frame(frame):
    df_tensor = torch.tensor(frame, device=device).float()
    df_tensor = df_tensor.permute((0, 3, 1, 2))
    for i in range(len(df_tensor)):
        df_tensor[i] = normalize_data()["vid"](df_tensor[i] / 255.0)
    return df_tensor
