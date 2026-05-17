"""One-shot smoke test: connect to Braintrust, log a dummy span, surface errors.

Run from the project root:
    uv run python scripts/smoke_braintrust.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("BRAINTRUST_API_KEY", "").strip()
project = os.environ.get("BRAINTRUST_PROJECT", "nba-rag").strip()

print(f"API key present: {bool(api_key)} (len={len(api_key)})")
print(f"Project name:    {project!r}")

if not api_key:
    print("ERROR: BRAINTRUST_API_KEY is empty. Set it in .env and re-run.")
    sys.exit(1)

try:
    import braintrust
    from importlib.metadata import version, PackageNotFoundError

    try:
        sdk_ver = version("braintrust")
    except PackageNotFoundError:
        sdk_ver = "unknown"
    print(f"braintrust SDK:  {sdk_ver}")
except ImportError:
    print("ERROR: braintrust SDK not installed. Run `uv add braintrust`.")
    sys.exit(1)

try:
    logger = braintrust.init_logger(project=project)
    print(f"Logger created.  org_id={getattr(logger, '_org_id', '?')!r}")
    span = logger.start_span(name="smoke-test")
    span.log(
        input={"q": "smoke test"},
        output={"a": "ok"},
        metadata={"origin": "scripts/smoke_braintrust.py"},
    )
    span.end()
    logger.flush()
    print(f"OK: wrote one event to project {project!r}. Refresh braintrust.dev.")
except Exception as e:
    print(f"ERROR ({type(e).__name__}): {e}")
    sys.exit(2)
