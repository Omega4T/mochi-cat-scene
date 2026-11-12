"""Write the entry's picture to $MAKEFUN_OUTPUT_DIR (or /output) as entry.png.

The artwork is rendered by the deterministic Pillow program in tools/ (see tools/render.py);
this entrypoint ships the finished piece and copies its bytes, which the rules allow. A copy
keeps the two grading runs byte-identical, and the guard below fails loudly if the asset is
missing or is not the size the gate wants, instead of writing a broken entry.
"""
import os
import pathlib
import shutil
import sys

MAX_BYTES = 1048576
SRC = pathlib.Path(__file__).resolve().parent / "asset" / "entry.png"


def main() -> int:
    if not SRC.is_file():
        print(f"asset missing: {SRC}", file=sys.stderr)
        return 1
    payload = SRC.read_bytes()
    if not payload or len(payload) > MAX_BYTES:
        print(f"asset is {len(payload)} bytes, the gate allows {MAX_BYTES}", file=sys.stderr)
        return 1
    out_dir = pathlib.Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, out_dir / "entry.png")
    print(f"wrote {out_dir / 'entry.png'} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
