"""
RepoMind Agent
Given a natural-language question, retrieves semantically relevant code
chunks from Endee and synthesizes an answer using Google Gemini.
"""

import logging
from dataclasses import dataclass

import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from endee import Endee

from config import (
    ENDEE_HOST,
    ENDEE_AUTH_TOKEN,
    INDEX_NAME,
    TOP_K,
    GOOGLE_API_KEY,
    LLM_MODEL,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


@dataclass
class CodeResult:
    file: str
    start_line: int
    end_line: int
    language: str
    snippet: str
    similarity: float


SYSTEM_PROMPT = """You are RepoMind, an expert AI assistant specialized in answering questions about codebases.

You are given:
1. A developer's question about the codebase
2. Relevant code snippets retrieved from a vector database (Endee), ranked by semantic similarity

Your job:
- Answer the question clearly and concisely, referencing specific files and line numbers
- Point out patterns, potential issues, or architectural insights where relevant
- If the retrieved snippets are insufficient, say so honestly
- Format code references as: `filename.py:L12-34`

Be direct and developer-friendly. No fluff."""


def format_context(results: list[CodeResult]) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"[{i}] {r.file}:L{r.start_line}-{r.end_line} "
            f"(similarity={r.similarity:.3f}, lang={r.language})\n"
            f"```{r.language}\n{r.snippet}\n```"
        )
    return "\n\n".join(blocks)


class RepoMindAgent:
    def __init__(self):
        log.info("Initializing RepoMind agent ...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        client = Endee(ENDEE_AUTH_TOKEN) if ENDEE_AUTH_TOKEN else Endee()
        client.set_base_url(f"{ENDEE_HOST}/api/v1")
        self.index = client.get_index(INDEX_NAME)

        self._configure_llm(GOOGLE_API_KEY)
        log.info("Agent ready.")

    def _configure_llm(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API key is required")
        genai.configure(api_key=api_key)
        self.llm = genai.GenerativeModel(
            model_name=LLM_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

    def set_api_key(self, api_key: str):
        """Update the Gemini API key at runtime (e.g., passed from UI)."""
        self._configure_llm(api_key)

    def retrieve(self, question: str, top_k: int = TOP_K) -> list[CodeResult]:
        vector = self.model.encode(question).tolist()
        raw = self.index.query(vector=vector, top_k=top_k)

        results = []
        for item in raw:
            if isinstance(item, dict):
                m = item.get("meta", {}) or {}
                sim = item.get("similarity", 0.0)
            else:
                m = getattr(item, "meta", {}) or {}
                sim = getattr(item, "similarity", 0.0)

            results.append(CodeResult(
                file=m.get("file", "unknown"),
                start_line=m.get("start_line", 0),
                end_line=m.get("end_line", 0),
                language=m.get("language", ""),
                snippet=m.get("snippet", ""),
                similarity=sim,
            ))
        return results

    def answer(self, question: str, top_k: int = TOP_K) -> dict:
        log.info(f"Question: {question!r}")
        results = self.retrieve(question, top_k)

        if not results:
            return {
                "question": question,
                "answer": "No relevant code found in the indexed codebase.",
                "sources": [],
            }

        context = format_context(results)
        user_message = (
            f"Question: {question}\n\n"
            f"Relevant code snippets from the codebase:\n\n{context}"
        )

        response = self.llm.generate_content(user_message)
        answer_text = response.text
        log.info("Answer generated.")

        return {
            "question": question,
            "answer": answer_text,
            "sources": [
                {
                    "file": r.file,
                    "lines": f"{r.start_line}-{r.end_line}",
                    "similarity": round(r.similarity, 4),
                }
                for r in results
            ],
        }


def run_interactive():
    agent = RepoMindAgent()
    print("\n=== RepoMind — Codebase Q&A Agent ===")
    print("Type your question, or 'quit' to exit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question or question.lower() in {"quit", "exit"}:
            print("Bye!")
            break

        result = agent.answer(question)
        print(f"\nRepoMind:\n{result['answer']}\n")
        print("Sources:")
        for s in result["sources"]:
            print(f"  • {s['file']}:L{s['lines']} (similarity={s['similarity']})")
        print()


if __name__ == "__main__":
    run_interactive()