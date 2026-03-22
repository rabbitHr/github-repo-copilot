"""
DevMind Indexer
Walks a codebase, chunks source files, generates embeddings,
and upserts them into Endee vector database.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Generator

from sentence_transformers import SentenceTransformer
from endee import Endee, Precision

from config import (
    ENDEE_HOST,
    ENDEE_AUTH_TOKEN,
    INDEX_NAME,
    EMBEDDING_DIM,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    SUPPORTED_EXTENSIONS,
    EXCLUDE_DIRS,
    BATCH_SIZE,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def iter_source_files(root: str) -> Generator[Path, None, None]:
    """Yield all supported source files under root, skipping excluded dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            path = Path(dirpath) / fname
            if path.suffix in SUPPORTED_EXTENSIONS:
                yield path


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping line-based chunks."""
    lines = text.splitlines(keepends=True)
    chunks = []
    start = 0
    while start < len(lines):
        end = min(start + size, len(lines))
        chunk = "".join(lines[start:end])
        chunks.append((start + 1, end, chunk))  # (start_line, end_line, text)
        if end == len(lines):
            break
        start += size - overlap
    return chunks


def make_chunk_id(filepath: str, start_line: int) -> str:
    """Deterministic ID for a chunk so re-indexing is idempotent."""
    raw = f"{filepath}:{start_line}"
    return hashlib.md5(raw.encode()).hexdigest()


def build_index(client: Endee):
    """Create the Endee index if it doesn't already exist."""
    raw_indexes = client.list_indexes()
    existing = []
    for idx in raw_indexes:
        if isinstance(idx, str):
            existing.append(idx)
        elif hasattr(idx, "name"):
            existing.append(idx.name)
        elif isinstance(idx, dict) and "name" in idx:
            existing.append(idx["name"])
    if INDEX_NAME not in existing:
        log.info(f"Creating index '{INDEX_NAME}' (dim={EMBEDDING_DIM})")
        try:
            client.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                space_type="cosine",
                precision=Precision.INT8,
            )
        except Exception as e:
            # If another process already created it, continue; otherwise re-raise
            if "already exists" not in str(e).lower():
                raise
            log.info(f"Index '{INDEX_NAME}' now exists (race); proceeding.")
    else:
        log.info(f"Index '{INDEX_NAME}' already exists — will upsert.")


def index_codebase(repo_path: str):
    """Main entry point: index an entire codebase into Endee."""
    repo_path = os.path.abspath(repo_path)
    log.info(f"Indexing codebase: {repo_path}")

    # Connect to Endee
    client = Endee(ENDEE_AUTH_TOKEN) if ENDEE_AUTH_TOKEN else Endee()
    client.set_base_url(f"{ENDEE_HOST}/api/v1")
    build_index(client)
    index = client.get_index(INDEX_NAME)

    # Load embedding model
    log.info("Loading embedding model …")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    files = list(iter_source_files(repo_path))
    log.info(f"Found {len(files)} source files.")

    batch = []
    total_chunks = 0

    for filepath in files:
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            log.warning(f"Skipping {filepath}: {e}")
            continue

        rel_path = str(filepath.relative_to(repo_path))
        chunks = chunk_text(text)

        for start_line, end_line, chunk_text_content in chunks:
            if not chunk_text_content.strip():
                continue

            vector = model.encode(chunk_text_content).tolist()
            chunk_id = make_chunk_id(rel_path, start_line)

            batch.append({
                "id": chunk_id,
                "vector": vector,
                "meta": {
                    "file": rel_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": filepath.suffix.lstrip("."),
                    "snippet": chunk_text_content[:300],
                },
            })

            if len(batch) >= BATCH_SIZE:
                index.upsert(batch)
                total_chunks += len(batch)
                log.info(f"Upserted {total_chunks} chunks so far …")
                batch = []

    if batch:
        index.upsert(batch)
        total_chunks += len(batch)

    log.info(f"Done! Indexed {total_chunks} chunks from {len(files)} files.")
    return total_chunks


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    index_codebase(path)
