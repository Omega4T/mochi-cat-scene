"""Write the entry's picture to $MAKEFUN_OUTPUT_DIR (or /output) as entry.png.

The artwork was rendered by a deterministic Pillow program (kept in the repository's
tools/ directory, see render.py); this entrypoint ships the finished piece and copies
it, which the rules allow explicitly. Copying bytes keeps the two grading runs identical.
"""
import os
import pathlib
import shutil

root = pathlib.Path(__file__).resolve().parent
out_dir = pathlib.Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
out_dir.mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / "asset" / "entry.png", out_dir / "entry.png")
print("wrote", out_dir / "entry.png")
