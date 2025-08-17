from torch import Tensor
import torch
from singer_identity.model import IdentityEncoder

class EmbeddingGenerator:
    def __init__(self, model: IdentityEncoder):
        self.device = next(model.parameters()).device
        self.model = model.to(self.device)
        # set model to evaluation mode
        # basically just prevents self-training
        self.model.eval()

    def generate_embedding(self, wav: Tensor, projecting:bool=False) -> Tensor:
        wav = self.normalize_audio(wav)

        with torch.no_grad():
            features = self.model.encoder(self.model.feature_extractor(wav))
            if projecting:
                features = self.model.projection(features)

        return features

    def normalize_audio(self, wav: Tensor) -> Tensor:
        wav = wav[0]  # assuming mono audio, take the first channel
        wav = wav / torch.max(torch.abs(wav))  # normalize the audio
        wav = wav.to(self.device)  # move to the same device as the model
        return wav
