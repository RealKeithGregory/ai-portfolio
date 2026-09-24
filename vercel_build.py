"""Bake the pinned embedding model into the Vercel deployment bundle.

Vercel runs this after installing the dependencies and before the bundle is
sealed, which is the only moment a deployment can write files that the
running function will be able to read: a Vercel Function's filesystem is
read-only apart from /tmp, and /tmp does not survive between instances.

It is the direct equivalent of the `RUN python -c "import search;
search.load_model()"` line in the Dockerfile, and it exists for the same two
reasons: a cold start reads the weights from local disk instead of fetching
87 MB from the Hugging Face Hub, and the running function needs no network
access at all. A build fails here rather than a function failing to start in
production.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

CACHE = Path(__file__).parent / "hf-cache"

# Where the weights go. search.py points HF_HOME at this directory at import
# time when it exists, so the build and the runtime agree on one location
# without either of them naming an absolute deployment path.
os.environ["HF_HOME"] = str(CACHE)

# The build is the one place that is allowed to reach the Hub. Everywhere
# else HF_HUB_OFFLINE=1 makes a download impossible.
os.environ.pop("HF_HUB_OFFLINE", None)

import search  # noqa: E402  (imported after the environment is set)


def flatten_symlinks(root):
    """Replace the cache's symlinks with the files they point at.

    huggingface_hub stores one copy of every file under blobs/ and symlinks
    it into snapshots/<revision>/. That is the right layout for a cache
    shared by several revisions, but a deployment bundle is packed by
    copying files, and a symlink into a sibling directory does not reliably
    survive the trip -- it would surface as a failed cold start in
    production rather than as a failed build here.

    So each symlink becomes the real file, and the blobs it pointed at are
    dropped afterwards: nothing else in this cache refers to them, and
    keeping both would mean shipping the model twice.
    """
    replaced = 0
    for link in [p for p in root.rglob("*") if p.is_symlink()]:
        target = link.resolve()
        if not target.is_file():
            sys.exit(f"{link} points at {target}, which is not a file.")
        link.unlink()
        shutil.copy2(target, link)
        replaced += 1

    for blobs in root.rglob("blobs"):
        if blobs.is_dir():
            shutil.rmtree(blobs)

    # Lock files and the xet chunk cache are download-time scaffolding.
    for scaffolding in list(root.rglob(".locks")) + list(root.rglob("xet")):
        if scaffolding.is_dir():
            shutil.rmtree(scaffolding)

    return replaced


def directory_bytes(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def main():
    print(f"Fetching {search.MODEL_NAME} at {search.MODEL_REVISION[:12]}", flush=True)
    model = search.load_model()

    # Prove the weights work before they are sealed into the bundle, rather
    # than discovering it on the first search in production.
    shape = model.encode(["portfolio"], normalize_embeddings=True).shape
    print(f"Model loaded, embedding shape {shape}", flush=True)

    if not CACHE.is_dir():
        sys.exit(f"Expected the weights under {CACHE}, but it does not exist.")

    print(f"Flattened {flatten_symlinks(CACHE)} symlink(s)", flush=True)

    remaining = [p for p in CACHE.rglob("*") if p.is_symlink()]
    if remaining:
        sys.exit(f"{len(remaining)} symlink(s) still under {CACHE.name}.")

    # The real test of the offline setting: a fresh interpreter, the same
    # cache, and no way to ask the Hub for anything. This is what the
    # function will do on its first search.
    print("Re-loading with HF_HUB_OFFLINE=1, as production will", flush=True)
    offline = subprocess.run(
        [sys.executable, "-c", "import search; print(search.load_model().device)"],
        env={**os.environ, "HF_HUB_OFFLINE": "1"},
        capture_output=True,
        text=True,
    )
    if offline.returncode != 0:
        sys.exit(f"Offline load failed:\n{offline.stdout}\n{offline.stderr}")

    print(f"Weights baked into {CACHE.name}/: {directory_bytes(CACHE) / 1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
