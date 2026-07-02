"""Build/refresh the E2B template used by the 'e2b_full' worker backend
(qea.worker_e2b). The template bakes Python 3.12 + NexAU@v0.3.9 + ddgs into the image
so a worker sandbox starts in ~1-2s with NO per-sandbox pip install — required for
20-way concurrency. Run once (and again whenever the pinned deps change):

    .venv-nexau/bin/python scripts/build_e2b_template.py

Needs E2B_API_KEY (loaded from .env). Prints the resulting template id/alias.
"""
import os
import time
from pathlib import Path

# ubuntu:24.04 ships Python 3.12 (NexAU requires >=3.12; the default E2B base has 3.11).
# NexAU is pinned to the SAME git commit the local .venv-nexau uses (v0.3.9 / 35ee1861);
# ddgs is the web_search dependency (not in NexAU's own deps).
DOCKERFILE = """\
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
        python3 python3-pip python3-venv git curl ca-certificates && \\
    rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages --no-cache-dir \\
        "git+https://github.com/nex-agi/NexAU.git@v0.3.9" \\
        ddgs && \\
    python3 -c "import nexau; print('nexau OK', nexau.__file__)"
WORKDIR /home/user
"""

TEMPLATE_NAME = os.environ.get("QEA_E2B_TEMPLATE", "qea-nexau-worker")


def _load_dotenv() -> None:
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    _load_dotenv()
    from e2b import Template

    t0 = time.time()
    tmpl = Template().from_dockerfile(DOCKERFILE)
    print(f"building E2B template '{TEMPLATE_NAME}' (2 CPU / 2048 MB)...", flush=True)

    def _log(entry):
        print(f"[{time.time()-t0:5.0f}s] {getattr(entry, 'message', entry)}", flush=True)

    info = Template.build(tmpl, TEMPLATE_NAME, cpu_count=2, memory_mb=2048, on_build_logs=_log)
    print(f"BUILD DONE in {time.time()-t0:.0f}s: {info}", flush=True)


if __name__ == "__main__":
    main()
