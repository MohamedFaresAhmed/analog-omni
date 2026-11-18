"""Fail if any file in this repository contains a private model name.

The list of names is never stored here. Give it with one of:
  --names-file PATH             one name per line, '#' starts a comment
  OMNI_PRIVATE_NAMES_FILE=PATH  the same, as an environment variable
  OMNI_PRIVATE_NAMES="a,b c"    names separated by commas or white space (CI secret)

Names match as whole words, case-insensitively; letters, digits and '_' are
word characters. Both the working tree (tracked files and untracked files that
are not ignored) and the staged content in the index are scanned, file paths
included. Hits are reported by the name's line in the names file (or its
position in OMNI_PRIVATE_NAMES), not by the name, so the output is safe to
show in a public CI log; --show-names prints the names for local use.

Exit codes: 0 clean, 1 private name found, 2 no usable name list or git error.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

WORD = re.compile(r"[A-Za-z0-9_]+")


def load_names(args):
    """Return [(label, name)], label being the line number or list position."""
    path = args.names_file or os.environ.get("OMNI_PRIVATE_NAMES_FILE")
    names = []
    if path:
        for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            text = line.split("#", 1)[0].strip()
            if text:
                names.append((f"line {number}", text))
    elif os.environ.get("OMNI_PRIVATE_NAMES"):
        parts = re.split(r"[\s,]+", os.environ["OMNI_PRIVATE_NAMES"].strip())
        names = [(f"entry {i}", p) for i, p in enumerate(parts, 1) if p]
    for label, name in names:
        if not WORD.fullmatch(name):
            sys.exit(f"check_private_names: {label} of the name list is not a single word")
    return names


def git(root, *argv):
    result = subprocess.run(["git", *argv], cwd=root, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"check_private_names: git {' '.join(argv)} failed: "
                 f"{result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def working_tree(root):
    out = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for rel in sorted(set(p for p in out.decode("utf-8").split("\0") if p)):
        path = root / rel
        if path.is_file():
            yield rel, path.read_bytes()


def index(root):
    out = git(root, "ls-files", "-z", "--stage")
    entries = []
    for item in out.decode("utf-8").split("\0"):
        if item:
            meta, rel = item.split("\t", 1)
            mode, sha, _stage = meta.split()
            if mode != "160000":  # skip submodules
                entries.append((rel, sha))
    if not entries:
        return
    batch = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True,
                           input="".join(f"{sha}\n" for _, sha in entries).encode())
    if batch.returncode != 0:
        sys.exit("check_private_names: git cat-file --batch failed")
    data, pos = batch.stdout, 0
    for rel, _sha in entries:
        header_end = data.index(b"\n", pos)
        size = int(data[pos:header_end].split()[2])
        start = header_end + 1
        yield rel, data[start:start + size]
        pos = start + size + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--names-file", help="file with one private name per line")
    parser.add_argument("--root", help="repository root (default: this script's repository)")
    parser.add_argument("--show-names", action="store_true", help="print matched names (local use only)")
    args = parser.parse_args()

    names = load_names(args)
    if not names:
        print("check_private_names: no name list given; refusing to report the repository clean.",
              file=sys.stderr)
        return 2
    label_of = {name.lower(): label for label, name in names}
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(n) for n in sorted(label_of, key=len, reverse=True))
        + r")(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )

    start = Path(args.root) if args.root else Path(__file__).resolve().parent
    root = Path(git(start, "rev-parse", "--show-toplevel").decode().strip())

    hits, scanned = [], 0
    for source, items in (("working tree", working_tree(root)), ("index", index(root))):
        for rel, data in items:
            scanned += 1
            for m in pattern.finditer(rel):
                hits.append((source, rel, 0, m.group(1)))
            text = data.decode("latin-1")
            for m in pattern.finditer(text):
                hits.append((source, rel, text.count("\n", 0, m.start()) + 1, m.group(1)))

    for source, rel, line, word in hits:
        where = f"{rel} (path)" if line == 0 else f"{rel}:{line}"
        what = word if args.show_names else f"name at {label_of[word.lower()]}"
        print(f"PRIVATE NAME [{source}] {where}: {what}")
    if hits:
        print(f"check_private_names: FAILED, {len(hits)} hit(s) in {scanned} scanned files "
              f"against {len(names)} names.")
        return 1
    print(f"check_private_names: clean, {scanned} files scanned (working tree and index) "
          f"against {len(names)} names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
