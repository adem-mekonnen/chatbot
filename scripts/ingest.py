#!/usr/bin/env python3
"""
scripts/ingest.py — Knowledge-base ingestion pipeline.

Usage
-----
Normal run (fails if vectorstore already exists):
    python -m scripts.ingest

Overwrite an existing vectorstore explicitly:
    python -m scripts.ingest --overwrite

Override knowledge-base directory:
    python -m scripts.ingest --kb-dir ./data/my_docs

Environment variables (optional — all have safe defaults):
    CHROMA_PERSIST_DIR   Path where ChromaDB persists data  (default: ./vectorstore)
    CHROMA_COLLECTION    ChromaDB collection name           (default: enterprise_docs)
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


# ── Chunk tuning ─────────────────────────────────────────────────────────────
# 1200-char chunks with 150-char overlap give better retrieval relevance for
# policy-length PDF paragraphs than the previous 500/50 settings.
# Adjust per your document density and LLM context window.
CHUNK_SIZE    = 1200
CHUNK_OVERLAP = 150


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed knowledge-base documents into ChromaDB."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Delete and rebuild the existing vectorstore. "
            "Without this flag the script aborts if the vectorstore directory already exists, "
            "preventing accidental data loss in production."
        ),
    )
    parser.add_argument(
        "--kb-dir",
        default="./data/knowledge_base",
        metavar="PATH",
        help="Directory to scan for .txt and .pdf files (default: ./data/knowledge_base).",
    )
    return parser.parse_args()


def _load_documents(kb_dir: str) -> list:
    """Walk kb_dir, load every .txt and .pdf file, return raw Document list."""
    # Lazy imports — keep module-level side-effects out of the FastAPI startup path
    # when this module is imported as `python -m scripts.ingest`.
    from langchain_community.document_loaders import TextLoader, PyPDFLoader

    documents = []
    errors    = []

    kb_path = Path(kb_dir)
    if not kb_path.exists():
        kb_path.mkdir(parents=True, exist_ok=True)
        print(f"Created knowledge-base directory: {kb_dir}")

    all_files = [
        p for p in kb_path.rglob("*")
        if p.suffix.lower() in (".txt", ".pdf")
    ]

    if not all_files:
        print(f"Ingestion aborted: no .txt or .pdf files found in '{kb_dir}'.")
        sys.exit(0)

    print(f"Found {len(all_files)} file(s) to process.")

    for file_path in all_files:
        try:
            if file_path.suffix.lower() == ".txt":
                loader = TextLoader(str(file_path), encoding="utf-8")
            else:
                loader = PyPDFLoader(str(file_path))
            docs = loader.load()
            documents.extend(docs)
            print(f"  ✓  {file_path.name}  ({len(docs)} page/section(s))")
        except Exception as exc:
            errors.append(file_path.name)
            print(f"  ✗  {file_path.name}  — {exc}")

    if errors:
        print(f"\nWarning: {len(errors)} file(s) failed to load and were skipped.")

    return documents


def main() -> None:
    args       = _parse_args()
    persist_dir     = os.getenv("CHROMA_PERSIST_DIR", "./vectorstore")
    collection_name = os.getenv("CHROMA_COLLECTION",  "enterprise_docs")
    kb_dir          = args.kb_dir

    print("=" * 60)
    print(" Enterprise Knowledge-Base Ingestion Pipeline")
    print("=" * 60)
    print(f"  Knowledge base : {kb_dir}")
    print(f"  Vectorstore    : {persist_dir}")
    print(f"  Collection     : {collection_name}")
    print(f"  Chunk size     : {CHUNK_SIZE} chars  (overlap {CHUNK_OVERLAP})")
    print()

    # ── Overwrite guard ───────────────────────────────────────────────────────
    # Without --overwrite the script aborts when the directory already exists.
    # This prevents an accidental `python -m scripts.ingest` from silently
    # destroying a production vectorstore.
    if Path(persist_dir).exists():
        if not args.overwrite:
            print(
                f"ERROR: Vectorstore already exists at '{persist_dir}'.\n"
                f"       Pass --overwrite to delete and rebuild it, or choose a different path.\n"
                f"       Aborting to protect existing data."
            )
            sys.exit(1)
        else:
            print(f"--overwrite flag set: removing existing vectorstore at '{persist_dir}'…")
            shutil.rmtree(persist_dir)
            print("  Existing vectorstore removed.")

    # ── Load documents ────────────────────────────────────────────────────────
    print(f"\nScanning '{kb_dir}' for documents…")
    documents = _load_documents(kb_dir)

    if not documents:
        print("No documents loaded. Aborting.")
        sys.exit(1)

    print(f"\nLoaded {len(documents)} raw document(s).")

    # ── Split into chunks ─────────────────────────────────────────────────────
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunk(s)  "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}).")

    # ── Embed ─────────────────────────────────────────────────────────────────
    # HuggingFaceEmbeddings replaces the deprecated SentenceTransformerEmbeddings
    # from langchain_community, matching the import used in retriever.py.
    print("\nLoading embedding model (all-MiniLM-L6-v2)…")
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    print("  Embedding model ready.")

    # ── Write to ChromaDB with tqdm progress tracking ────────────────────────
    print(f"\nWriting {len(chunks)} chunk(s) to ChromaDB…")

    try:
        from tqdm import tqdm as _tqdm_available  # noqa: F401
        _has_tqdm = True
    except ImportError:
        _has_tqdm = False

    from langchain_chroma import Chroma

    if _has_tqdm:
        # Batch into groups of 100 so tqdm tracks insertion progress.
        from tqdm import tqdm

        BATCH = 100
        batches = [chunks[i : i + BATCH] for i in range(0, len(chunks), BATCH)]

        # Create the collection with the first batch, then add the rest.
        vectorstore = None
        for batch in tqdm(batches, desc="Embedding batches", unit="batch"):
            if vectorstore is None:
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    persist_directory=persist_dir,
                    collection_name=collection_name,
                )
            else:
                vectorstore.add_documents(batch)
    else:
        print("  (Install tqdm for progress tracking: pip install tqdm)")
        Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=persist_dir,
            collection_name=collection_name,
        )

    print(f"\n{'=' * 60}")
    print(f"  ✓  Vectorstore built: {len(chunks)} chunks indexed.")
    print(f"     Location  : {persist_dir}")
    print(f"     Collection: {collection_name}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
