import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv, find_dotenv
from e2b_code_interpreter import Sandbox, SandboxQuery, SandboxState

from .logger import logger

NEXTJS_TEMPLATE_ID = "dlai-nextjs-developer"


def load_env():
    load_dotenv(find_dotenv())


def get_openai_api_key() -> str:
    load_env()
    return os.getenv("OPENAI_API_KEY")


def setup_sandbox(sbx: Sandbox):
    entries = sbx.files.list("")
    has_file = [e for e in entries if e.name == "sbx_tools.py"]
    if has_file:
        return
    logger.info("[sandbox] 🔧 Setting up sandbox...")
    sbx.run_code("pip install rapidfuzz", language="bash")
    sbx_tools_path = Path(__file__).parent / "sbx_tools.py"
    with open(sbx_tools_path, "r") as f:
        content = f.read()
    sbx.files.write("sbx_tools.py", content)
    sbx.run_code("from sbx_tools import *")
    logger.info("[sandbox] 🔧 Done!")


def create_sandbox(
    cache_file: str,
    template: str = None,
    overwrite: bool = False,
) -> Sandbox:
    cache_path = Path(cache_file)

    if cache_path.exists():
        name = cache_path.read_text().strip()
    else:
        label = template if template else "default"
        name = f"dlai-sbx-{label}-{uuid4()}"
        cache_path.write_text(name)

    if not overwrite:
        running = Sandbox.list(
            SandboxQuery(metadata={"name": name}, state=[SandboxState.RUNNING])
        ).next_items()
        if running:
            sandbox = Sandbox.connect(running[0].sandbox_id)
            logger.info(f"[sandbox] 🔌 Reconnecting to {sandbox.sandbox_id}")
            return sandbox

    kwargs = {}
    if template:
        kwargs["template"] = template

    sandbox = Sandbox.create(
        timeout=60 * 60,
        metadata={"name": name},
        **kwargs,
    )
    logger.info(f"[sandbox] 🚀 Created {sandbox.sandbox_id}")
    return sandbox


def clear_sandboxes():
    paginator = Sandbox.list(SandboxQuery(state=[SandboxState.RUNNING]))
    try:
        while sandboxes := paginator.next_items():
            for s in sandboxes:
                Sandbox.connect(s.sandbox_id).kill()
                logger.info(f"[sandbox] Killed {s.sandbox_id}")
    except Exception:
        pass
