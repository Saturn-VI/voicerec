import base64
import binascii
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
import typing

import bcrypt
import numpy as np
import torch
from torch.nn import CosineSimilarity
import torchaudio.transforms as T
from litestar import Litestar, Request, Response, get, post
from litestar.di import Provide
from litestar.static_files import create_static_files_router
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND
from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.stores.file import FileStore
from torch import Tensor
from torchcodec.decoders import AudioDecoder, AudioStreamMetadata

from ml import EmbeddingGenerator
from singer_identity.model import IdentityEncoder, load_model

HTML_DIR = Path("website")
VOICE_SIMILARITY_THRESHOLD = 0.85

@dataclass
class CredentialData:
    username: str
    password: str
    audio_data: str # should be base64 encoded audio data as webm

@dataclass
class User:
    username: str
    password: bytes # should be hashed
    embedding: Tensor

    def to_dict(self) -> Dict[str, Any]:
        embedding_np = self.embedding.cpu().numpy()
        return {
            'username': self.username,
            'password': base64.b64encode(self.password).decode('utf-8'),
            'embedding': base64.b64encode(embedding_np.tobytes()).decode('utf-8'),
            'embedding_shape': list(self.embedding.shape),
            'embedding_dtype': str(embedding_np.dtype)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        password_bytes = base64.b64decode(data['password'])

        embedding_bytes = base64.b64decode(data['embedding'])
        embedding_shape = data['embedding_shape']
        embedding_dtype = data['embedding_dtype']

        embedding_np = np.frombuffer(embedding_bytes, dtype=np.dtype(embedding_dtype)).reshape(embedding_shape)
        embedding_tensor = torch.from_numpy(embedding_np.copy())

        return cls(
            username=data['username'],
            password=password_bytes,
            embedding=embedding_tensor
        )

embedding_generator: EmbeddingGenerator
cos_sim: CosineSimilarity

async def embedding_generator_provider() -> EmbeddingGenerator:
    global embedding_generator
    return embedding_generator

async def cos_sim_provider() -> CosineSimilarity:
    global cos_sim
    return cos_sim

async def on_startup() -> None:
    Path("database").mkdir(parents=True, exist_ok=True)

    model = load_model("byol")
    if (isinstance(model, IdentityEncoder)):
        global embedding_generator
        embedding_generator = EmbeddingGenerator(model)
    else:
        raise ValueError("Model is not an IdentityEncoder")

    global cos_sim
    cos_sim = CosineSimilarity(dim=1)

@get("/hello")
async def hello() -> str:
    return "Hello, World!"

@post("/account/create", status_code=HTTP_201_CREATED)
async def account_create(request: Request, data: CredentialData) -> Response[str]:
    file_store = app.stores.get("users")
    if await file_store.exists(data.username):
        # user already exists
        return Response("User already exists", status_code=HTTP_400_BAD_REQUEST)

    embedding_generator = await embedding_generator_provider()

    try:
        webm_bytes = base64.b64decode(data.audio_data)
    except binascii.Error as e:
        print("Error decoding base64 audio data:", e)
        return Response("Invalid audio data", status_code=HTTP_400_BAD_REQUEST)

    try:
        audio_decoder = AudioDecoder(source=webm_bytes)
        samples = audio_decoder.get_all_samples()
        wav = torch.cat([w.data for w in samples if isinstance(w, Tensor)])
        sample_rate = typing.cast(AudioStreamMetadata, audio_decoder.metadata).sample_rate or 0
    except Exception as e:
        print("Error loading audio data:", e)
        return Response("Invalid audio data", status_code=HTTP_400_BAD_REQUEST)

    if sample_rate != 44100:
        resampler = T.Resample(orig_freq=sample_rate, new_freq=44100)
        wav = resampler(wav)

    user: User = User(
        username = data.username,
        password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()),
        embedding = embedding_generator.generate_embedding(wav)
    )

    user_data = user.to_dict()
    user_json = json.dumps(user_data).encode('utf-8')
    await file_store.set(user.username, user_json)

    if not request.session:
        request.set_session({"username": user.username})

    return Response("Account created successfully", status_code=HTTP_201_CREATED)

@post("/account/login")
async def account_login(request: Request, data: CredentialData) -> Response[str]:
    file_store = app.stores.get("users")

    if not await file_store.exists(data.username):
        # user does not exist
        return Response("Invalid credentials", status_code=HTTP_401_UNAUTHORIZED)

    user_json = await file_store.get(data.username)
    if user_json is None:
        # user data not found
        return Response("Data not found", status_code=HTTP_404_NOT_FOUND)

    try:
        user_data = json.loads(user_json.decode('utf-8'))
        user = User.from_dict(user_data)
    except Exception as e:
        print("Error deserializing user data:", e)
        return Response("Internal server error", status_code=500)

    if not bcrypt.checkpw(data.password.encode('utf-8'), user.password):
        return Response("Invalid credentials", status_code=HTTP_401_UNAUTHORIZED)

    embedding_generator = await embedding_generator_provider()

    try:
        webm_bytes = base64.b64decode(data.audio_data)
    except binascii.Error as e:
        print("Error decoding base64 audio data:", e)
        return Response("Invalid audio data", status_code=HTTP_400_BAD_REQUEST)

    try:
        audio_decoder = AudioDecoder(source=webm_bytes)
        samples = audio_decoder.get_all_samples()
        wav = torch.cat([w.data for w in samples if isinstance(w, Tensor)])
        sample_rate = typing.cast(AudioStreamMetadata, audio_decoder.metadata).sample_rate or 0
    except Exception as e:
        print("Error loading audio data:", e)
        return Response("Invalid audio data", status_code=HTTP_400_BAD_REQUEST)

    if sample_rate != 44100:
        resampler = T.Resample(orig_freq=sample_rate, new_freq=44100)
        wav = resampler(wav)

    similarity = (await cos_sim_provider())(user.embedding, embedding_generator.generate_embedding(wav)).item()
    if similarity < VOICE_SIMILARITY_THRESHOLD:
        return Response("Invalid credentials", status_code=HTTP_401_UNAUTHORIZED)

    if not request.session:
        request.set_session({"username": user.username})

    return Response(json.dumps({"similarity": similarity}), status_code=200)

@post("/account/logout")
async def account_logout(request: Request) -> Response[str]:
    if request.session:
        request.clear_session()
        return Response("Logged out successfully", status_code=HTTP_200_OK)
    else:
        return Response("No active session", status_code=HTTP_401_UNAUTHORIZED)

app = Litestar(
    route_handlers=[
        hello,
        account_create,
        account_login,
        account_logout,
        create_static_files_router(
            path="/",
            directories=[HTML_DIR],
            html_mode=True,
        ),
    ],
    middleware=[ServerSideSessionConfig().middleware],
    stores={"users": FileStore(Path("database"), create_directories=True)},
    dependencies={"embedding_generator": Provide(embedding_generator_provider), "cos_sim": Provide(cos_sim_provider)},
    on_startup=[on_startup],
)
