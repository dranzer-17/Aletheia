import torch
import torch.nn as nn
from .genconvit_ed import GenConViTED
from torchvision import transforms
import os

class GenConViT(nn.Module):
    def __init__(self, config, ed, vae, net, fp16):
        super(GenConViT, self).__init__()
        self.net = net
        self.fp16 = fp16
        import os
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ed_path = os.path.join(root_dir, 'weights', f'{ed}.pth')
        vae_path = os.path.join(root_dir, 'weights', f'{vae}.pth')

        if self.net=='ed':
            if not os.path.exists(ed_path):
                raise FileNotFoundError(f"Error: {ed_path} file not found.")
            try:
                self.model_ed = GenConViTED(config)
                self.checkpoint_ed = torch.load(ed_path, map_location=torch.device('cpu'))
                if 'state_dict' in self.checkpoint_ed:
                    self.model_ed.load_state_dict(self.checkpoint_ed['state_dict'], strict=False)
                else:
                    self.model_ed.load_state_dict(self.checkpoint_ed, strict=False)
                self.model_ed.eval()
                if self.fp16:
                    self.model_ed.half()
            except FileNotFoundError:
                raise FileNotFoundError(f"Error: {ed_path} file not found.")
        elif self.net=='vae':
            if not os.path.exists(vae_path):
                raise FileNotFoundError(f"Error: {vae_path} file not found.")
            try:
                from .genconvit_vae import GenConViTVAE
                self.model_vae = GenConViTVAE(config)
                self.checkpoint_vae = torch.load(vae_path, map_location=torch.device('cpu'))
                if 'state_dict' in self.checkpoint_vae:
                    self.model_vae.load_state_dict(self.checkpoint_vae['state_dict'], strict=False)
                else:
                    self.model_vae.load_state_dict(self.checkpoint_vae, strict=False)
                self.model_vae.eval()
                if self.fp16:
                    self.model_vae.half()
            except FileNotFoundError:
                raise FileNotFoundError(f"Error: {vae_path} file not found.")
        else:
            if not os.path.exists(ed_path):
                raise FileNotFoundError(f"Error: {ed_path} file not found.")
            if not os.path.exists(vae_path):
                raise FileNotFoundError(f"Error: {vae_path} file not found.")
            try:
                self.model_ed = GenConViTED(config)
                from .genconvit_vae import GenConViTVAE
                self.model_vae = GenConViTVAE(config)
                self.checkpoint_ed = torch.load(ed_path, map_location=torch.device('cpu'))
                self.checkpoint_vae = torch.load(vae_path, map_location=torch.device('cpu'))
                
                # Try to load with strict=False to handle architecture mismatches
                try:
                    if 'state_dict' in self.checkpoint_ed:
                        self.model_ed.load_state_dict(self.checkpoint_ed['state_dict'], strict=False)
                    else:
                        self.model_ed.load_state_dict(self.checkpoint_ed, strict=False)
                except Exception as e:
                    import logging
                    logging.warning(f"Partial load of ED weights (some layers may not match): {e}")
                
                try:
                    if 'state_dict' in self.checkpoint_vae:
                        self.model_vae.load_state_dict(self.checkpoint_vae['state_dict'], strict=False)
                    else:
                        self.model_vae.load_state_dict(self.checkpoint_vae, strict=False)
                except Exception as e:
                    import logging
                    logging.warning(f"Partial load of VAE weights (some layers may not match): {e}")
                
                self.model_ed.eval()
                self.model_vae.eval()
                if self.fp16:
                    self.model_ed.half()
                    self.model_vae.half()
            except FileNotFoundError:
                raise FileNotFoundError(f"Error: {ed_path} or {vae_path} file not found.")

    def forward(self, x):
        if self.net == 'ed':
            x = self.model_ed(x)
        elif self.net == 'vae':
            x, _ = self.model_vae(x)
        else:
            x1 = self.model_ed(x)
            x2, _ = self.model_vae(x)
            x = torch.cat((x1, x2), dim=0)  # Concatenate both model outputs
        return x
