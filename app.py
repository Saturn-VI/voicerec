import base64
import binascii
import io
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import bcrypt
import numpy as np
import torch
from torch.nn import CosineSimilarity
import torchaudio
import torchaudio.transforms as T
from litestar import Litestar, Response, get, post
from litestar.di import Provide
from litestar.static_files import create_static_files_router
from litestar.status_codes import HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED
from litestar.stores.file import FileStore
from torch import Tensor

from ml import EmbeddingGenerator
from singer_identity.model import IdentityEncoder, load_model

HTML_DIR = Path("website")

# the general login flow is:
# client submits credentials + 44 seconds of audio data
# if correct, the server returns an auth token

# create account flow
# client submits a username, password, and audio data (should be about 44 seconds)
# the account is created

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

file_store: FileStore
embedding_generator: EmbeddingGenerator

def embedding_generator_provider() -> EmbeddingGenerator:
    global embedding_generator
    return embedding_generator

def file_store_provider() -> FileStore:
    global file_store
    return file_store

async def on_startup() -> None:
    global file_store
    path = Path("database")
    path.mkdir(parents=True, exist_ok=True)
    file_store = FileStore(path, create_directories=True)
    await file_store.delete_expired()

    model = load_model("byol")
    if (isinstance(model, IdentityEncoder)):
        global embedding_generator
        embedding_generator = EmbeddingGenerator(model)
    else:
        raise ValueError("Model is not an IdentityEncoder")

@get("/hello")
async def hello() -> str:
    return "Hello, World!"

# create account
@post("/account/create", status_code=HTTP_201_CREATED)
async def account_create(data: CredentialData) -> Response[str]:
    if (not data.username or not isinstance(data.username, str)):
        return Response("Invalid username", status_code=HTTP_400_BAD_REQUEST)

    file_store = file_store_provider()
    if await file_store.exists(data.username):
        return Response("Username already exists", status_code=HTTP_400_BAD_REQUEST)

    embedding_generator = embedding_generator_provider()

    try:
        webm_bytes = base64.b64decode(data.audio_data)
        print(f"Successfully decoded base64 audio data. Size: {len(webm_bytes)} bytes")
        print(f"First 16 bytes (hex): {webm_bytes[:16].hex()}")
    except binascii.Error as e:
        print("Error decoding base64 audio data:", e)
        return Response("Invalid base64 audio data", status_code=HTTP_400_BAD_REQUEST)

    webm_stream = io.BytesIO(webm_bytes)

    try:
        wav, sample_rate = torchaudio.load(webm_stream)
    except Exception as e:
        print("Error loading audio data:", e)
        return Response("Invalid audio data format", status_code=HTTP_400_BAD_REQUEST)

    if sample_rate != 44100:
        print("Sample rate not 44100, resampling")
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
    return Response("Account created successfully", status_code=HTTP_201_CREATED)

@post("/account/login")
async def account_login(data: CredentialData) -> Response[str]:
    if not data.username or not isinstance(data.username, str):
        return Response("Invalid username", status_code=HTTP_400_BAD_REQUEST)

    file_store = file_store_provider()

    if not await file_store.exists(data.username):
        return Response("Invalid credentials", status_code=HTTP_400_BAD_REQUEST)

    user_json = await file_store.get(data.username)
    if user_json is None:
        return Response("Invalid credentials", status_code=HTTP_400_BAD_REQUEST)

    try:
        user_data = json.loads(user_json.decode('utf-8'))
        user = User.from_dict(user_data)
    except Exception as e:
        print("Error deserializing user data:", e)
        return Response("Internal server error", status_code=500)

    if not bcrypt.checkpw(data.password.encode('utf-8'), user.password):
        return Response("Invalid credentials", status_code=HTTP_400_BAD_REQUEST)

    embedding_generator = embedding_generator_provider()

    try:
        webm_bytes = base64.b64decode(data.audio_data)
    except binascii.Error as e:
        print("Error decoding base64 audio data:", e)
        return Response("Invalid base64 audio data", status_code=HTTP_400_BAD_REQUEST)

    webm_stream = io.BytesIO(webm_bytes)

    try:
        wav, sample_rate = torchaudio.load(webm_stream, format='webm')
    except Exception as e:
        print("Error loading audio data:", e)
        return Response("Invalid audio data format", status_code=HTTP_400_BAD_REQUEST)

    if sample_rate != 44100:
        print("Sample rate not 44100, resampling")
        resampler = T.Resample(orig_freq=sample_rate, new_freq=44100)
        wav = resampler(wav)

    cos = CosineSimilarity()
    if cos(user.embedding, embedding_generator.generate_embedding(wav)).item() < 0.9:
        return Response("Singing does not match", status_code=HTTP_401_UNAUTHORIZED)

    # TODO: Generate and return auth token
    return Response("Login successful", status_code=200)

app = Litestar(
    route_handlers=[
        hello,
        account_create,
        account_login,
        create_static_files_router(
            path="/",
            directories=[HTML_DIR],
            html_mode=True,
        ),
    ],
    dependencies={"embedding_generator": Provide(embedding_generator_provider), "file_store": Provide(file_store_provider)},
    on_startup=[on_startup],
)
