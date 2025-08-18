from pathlib import Path
from litestar import Litestar, get
from litestar.static_files import create_static_files_router

HTML_DIR = Path("website")

@get("/hello")
async def index() -> str:
    return "Hello, World!"

app = Litestar(
    route_handlers=[
        index,
        create_static_files_router(
            path="/",
            directories=[HTML_DIR],
            html_mode=True,
        ),
    ]
)
