#!/usr/bin/env python3
"""Fail the job when private source material shows up in public outputs.

Markers are derived from the private checkout (``--src``) at run time and are
only ever held as sha256 digests in memory: this script prints counts, never a
marker, a matched line or a file path from the private tree.

Checked targets:
  --log FILE      text that was echoed to the public Actions log (tee'd copy)
  --zip FILE      a release archive about to be uploaded/published
  --dir DIR       every file directly inside DIR (signed upload set)

Exit code 1 when any category has hits; 0 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

# Directories inside the private checkout that are not source (build output,
# tool checkouts, VCS metadata) and must not feed the marker set.
SKIP_DIRS = {".git", "dist", "build", ".local", "node_modules", ".venv", "__pycache__"}
# Top-level entries of the private repo that must never appear inside a package.
FORBIDDEN_TOP = {"server", "tests", "docs", "clipvault-ai-docs", ".github", ".git",
                 "AGENTS.md", "spec.md", "opencode.json", "compose.yaml", "Dockerfile"}
# Members larger than this are native binaries/archives; they hold no plaintext comments.
MAX_TEXT_MEMBER = 20 * 1024 * 1024
CODE_LINE_MIN = 30
COMMENT_LINE_MIN = 40
CREDENTIAL = re.compile(
    rb"ghs_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    rb"|x-access-token:|-----BEGIN [A-Z ]*PRIVATE KEY-----|vk1\.a\.")
TRACEBACK = re.compile(rb'Traceback \(most recent call last\)|File "[^"]+\.py", line \d+')
BINARY_ZIP = re.compile(r"clipvault-client-.+-(?:mac-arm64|macos-arm64|windows-x64)\.zip")


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


class Markers:
    def __init__(self, src: Path) -> None:
        self.code_lines: set[bytes] = set()
        self.comment_lines: set[bytes] = set()
        self.file_digests: set[bytes] = set()
        self.files = 0
        for path in src.rglob("*.py"):
            rel = path.relative_to(src)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            data = path.read_bytes()
            self.files += 1
            if len(data) > 200:
                self.file_digests.add(_digest(data))
            for raw in data.splitlines():
                line = raw.strip()
                if len(line) >= CODE_LINE_MIN:
                    self.code_lines.add(_digest(line))
                if line.startswith(b"#") and len(line) >= COMMENT_LINE_MIN:
                    self.comment_lines.add(_digest(line))


def _line_hits(data: bytes, wanted: set[bytes]) -> int:
    return sum(_digest(raw.strip()) in wanted for raw in data.splitlines() if raw.strip())


def _forbidden_member(name: str) -> bool:
    parts = [part for part in name.split("/") if part]
    if ".git" in parts or ".github" in parts or "clipvault-ai-docs" in parts:
        return True
    # Application roots: ClipVault/<top>, ClipVault/_internal/<top>,
    # clipvault-client/<top>, clipvault-client/versions/<v>/<top>.
    candidates = []
    if parts[:2] == ["ClipVault", "_internal"] and len(parts) > 2:
        candidates.append(parts[2])
    if parts[:1] == ["ClipVault"] and len(parts) > 1:
        candidates.append(parts[1])
    if parts[:2] == ["clipvault-client", "versions"] and len(parts) > 3:
        candidates.append(parts[3])
    if parts[:1] == ["clipvault-client"] and len(parts) > 1:
        candidates.append(parts[1])
    return any(top in FORBIDDEN_TOP for top in candidates)


def scan_zip(path: Path, markers: Markers, hits: Counter) -> None:
    binary = bool(BINARY_ZIP.fullmatch(path.name))
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if _forbidden_member(info.filename):
                hits["forbidden_path"] += 1
            if not binary:
                # The source channel ships client .py files by design; only the
                # path policy and credential shapes apply to it.
                if info.file_size <= MAX_TEXT_MEMBER and CREDENTIAL.search(archive.read(info)):
                    hits["credential_shape"] += 1
                continue
            if info.file_size > MAX_TEXT_MEMBER:
                continue
            data = archive.read(info)
            if _digest(data) in markers.file_digests:
                hits["private_source_file"] += 1
            if info.filename.endswith(".py") and info.filename.startswith(("ClipVault/_internal/clipvault/",
                                                                          "ClipVault/clipvault/")):
                hits["plain_client_py"] += 1
            hits["private_comment_line"] += _line_hits(data, markers.comment_lines)
            if CREDENTIAL.search(data):
                hits["credential_shape"] += 1


def scan_text(data: bytes, markers: Markers, hits: Counter) -> None:
    hits["private_code_line"] += _line_hits(data, markers.code_lines)
    hits["credential_shape"] += len(CREDENTIAL.findall(data))
    hits["traceback"] += len(TRACEBACK.findall(data))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--log", type=Path, action="append", default=[])
    parser.add_argument("--zip", type=Path, action="append", default=[])
    parser.add_argument("--dir", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    markers = Markers(args.src)
    hits: Counter = Counter()
    if markers.files == 0:
        hits["no_markers"] += 1  # a scan without markers proves nothing
    scanned = 0
    for log in args.log:
        if log.is_file():
            scan_text(log.read_bytes(), markers, hits)
            scanned += 1
    targets = list(args.zip)
    for folder in args.dir:
        targets += sorted(p for p in folder.glob("*") if p.is_file())
    for target in targets:
        scanned += 1
        if target.suffix == ".py":
            hits["plain_py_upload"] += 1
        elif zipfile.is_zipfile(target):
            scan_zip(target, markers, hits)
        elif target.stat().st_size <= MAX_TEXT_MEMBER:
            data = target.read_bytes()
            hits["private_comment_line"] += _line_hits(data, markers.comment_lines)
            hits["credential_shape"] += len(CREDENTIAL.findall(data))
    total = sum(hits.values())
    summary = " ".join(f"{key}={value}" for key, value in sorted(hits.items()) if value)
    # Counts only: never print markers, matched content or private paths.
    print(f"leak-scan: marker_files={markers.files} targets={scanned} hits={total} {summary}".rstrip())
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
