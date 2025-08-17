import torch
from torchcodec.decoders import AudioDecoder
from ml import EmbeddingGenerator
from singer_identity import load_model
from singer_identity.model import IdentityEncoder

# Server implementation notes:
# chunk the audio into 5 second chunks
# and then do a 1/n average of the features (similar to https://samwho.dev/reservoir-sampling/)
# we can then show the user how close they are to their stored embedding

audio_path = "test.wav"

model = load_model("byol")
print(model)
print(type(model))
if (isinstance(model, IdentityEncoder)):
    print("Model is an IdentityEncoder")

    # not entirely sure what this does?
    # TODO figure that out
    # https://github.com/SonyCSLParis/ssl-singer-identity/blob/24751d11c6c169adc53be906fd36560df447f974/eval.py#L162
    print("Setting up model for evaluation...")
    device = next(model.parameters()).device
    model = model.to(device)
    # set model to evaluation mode
    # basically just prevents self-training
    model.eval()
    with torch.no_grad():
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
        # if we were doing projection we would also do
            # features = model.projection(features)

        # the wavs come from the batch
        # through (wavs, others) = batch
        # then it does wavs = wavs.to(device)
        # so I just need to figure out how the dataloader gets wavs

        # dataloader is a torch dataloader which loads from test datasets
        # the test datasets are a bunch of EER_Eval_Dataset objects
        # after the enumerations and batch stuff,
        # each batch comes from __getitem__() in EER_Eval_Dataset
        # load comes from torchaudio

        # torchaudio.load returns a tensor and a sample rate
        # the paper normalizes the tensor by doing:
            # wav, _ = torchaudio.load(path)
            # this kills everything except the first channel
            # TODO make this not delete data (average stereo sound?)
            # wav = wav[0]
            # wav = wav / torch.max(torch.abs(wav))

        print("Loading audio from", audio_path)
        decoder = AudioDecoder(audio_path)
        wav = decoder.get_all_samples().data
        print("Audio loaded from", audio_path)

        EmbeddingGenerator = EmbeddingGenerator(model)
        print("Generating embedding...")
        features = EmbeddingGenerator.generate_embedding(wav)

        print("Features extracted successfully")
        print(features.shape)  # print the shape of the features tensor
        # print(features)

else:
    print("Bad bad bad")
