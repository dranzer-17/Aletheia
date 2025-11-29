import torch
from .genconvit import GenConViT

def load_genconvit(config, net, ed_weight, vae_weight, fp16):
    model = GenConViT(
        config,
        ed=ed_weight,
        vae=vae_weight,
        net=net,
        fp16=fp16
    )
    return model
