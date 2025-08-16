import torch
from singer_identity import load_model
from singer_identity.model import IdentityEncoder

model = load_model("byol")
print(model)
print(type(model))
if (isinstance(model, IdentityEncoder)):
    print("Model is an IdentityEncoder")

    # not entirely sure what this does?
    # TODO figure that out
    # https://github.com/SonyCSLParis/ssl-singer-identity/blob/24751d11c6c169adc53be906fd36560df447f974/eval.py#L162
    device = next(model.parameters()).device
    model = model.to(device)
    # set model to evaluation mode
    # basically just prevents self-training
    model.eval()
    with torch.no_grad():
        pass
        # it's business time
        # in the paper's code
        # it gets a batch from a torch dataloader
        # then creates (wavs, others) = batch
        # does a wavs = wavs.to(device)
        # then the output = self(wavs)
        # it seems like we can also call model(wavs)?
        # okay so the forward function for the similarityevaluator just does
        # features = model.encoder(model.feature_extractor(wavs))

        # so once we get the wavs, we can just do
        # features = model.encoder(model.feature_extractor(wavs))
        # if we were doing projection we would also do features = model.projection(features)

        # the wavs come from the batch
        # through (wavs, others) = batch
        # then it does wavs = wavs.to(device)
        # so I just need to figure out how the dataloader gets wavs

else:
    print("Bad bad bad")
