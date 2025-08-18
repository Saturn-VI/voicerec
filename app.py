from dataclasses import dataclass
from pathlib import Path
from litestar import Litestar, get, post
from litestar.static_files import create_static_files_router

HTML_DIR = Path("website")

# the general login flow is:
# client submits credentials + 30-45 seconds of audio data
# if correct, the server returns an auth token

# create account flow
# client submits a username, password, and audio data (should be about 45 seconds)
# the account is created

@dataclass
class CredentialData:
    username: str
    password: str
    audio_data: str # should be base64 encoded audio data

@get("/hello")
async def hello() -> str:
    return "Hello, World!"

# create account
# takes
@post("/account/create")
async def account_create(data: CredentialData) -> str:
    return "TODO"

@post("/account/login")
async def account_login(data: CredentialData) -> str:
    return "TODO"

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
    ]
)
