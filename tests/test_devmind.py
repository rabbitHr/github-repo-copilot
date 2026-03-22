"""
DevMind Tests
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
from indexer import chunk_text, make_chunk_id, iter_source_files
from pathlib import Path
import tempfile


# ── chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_basic():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = chunk_text(text, size=40, overlap=8)
    assert len(chunks) > 1
    # First chunk starts at line 1
    assert chunks[0][0] == 1
    # Each chunk has content
    for start, end, content in chunks:
        assert content.strip()


def test_chunk_text_small_file():
    text = "def hello():\n    return 'world'\n"
    chunks = chunk_text(text, size=40, overlap=8)
    assert len(chunks) == 1
    assert "hello" in chunks[0][2]


def test_chunk_text_overlap():
    text = "\n".join(f"line {i}" for i in range(50))
    chunks = chunk_text(text, size=20, overlap=5)
    # Verify overlap: end of chunk N overlaps with start of chunk N+1
    for i in range(len(chunks) - 1):
        _, end_line, _ = chunks[i]
        start_line, _, _ = chunks[i + 1]
        assert start_line < end_line  # overlap exists


def test_chunk_text_empty():
    chunks = chunk_text("", size=40, overlap=8)
    assert chunks == []


# ── make_chunk_id ─────────────────────────────────────────────────────────────

def test_chunk_id_deterministic():
    id1 = make_chunk_id("src/main.py", 10)
    id2 = make_chunk_id("src/main.py", 10)
    assert id1 == id2


def test_chunk_id_unique():
    id1 = make_chunk_id("src/main.py", 10)
    id2 = make_chunk_id("src/main.py", 50)
    id3 = make_chunk_id("src/utils.py", 10)
    assert id1 != id2
    assert id1 != id3


# ── iter_source_files ─────────────────────────────────────────────────────────

def test_iter_source_files(tmp_path):
    # Create fake repo structure
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils.js").write_text("console.log('hi')")
    (tmp_path / "README.md").write_text("# Readme")
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "lib.js").write_text("// ignored")

    files = list(iter_source_files(str(tmp_path)))
    paths = [f.name for f in files]

    assert "main.py" in paths
    assert "utils.js" in paths
    assert "README.md" not in paths   # .md not in SUPPORTED_EXTENSIONS
    assert "lib.js" not in paths      # inside node_modules


def test_iter_source_files_empty(tmp_path):
    files = list(iter_source_files(str(tmp_path)))
    assert files == []
