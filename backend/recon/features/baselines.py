from collections import Counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from recon import FEATURE_SCHEMA
from recon.errors import ReconError
from recon.schemas import FunctionAnalysis


def token_document(function: FunctionAnalysis) -> str:
    return " ".join(i.token for i in function.instructions)


def structure(function: FunctionAnalysis) -> list[float]:
    stats = function.cfg.statistics
    return [
        len(function.instructions),
        stats.get("blocks", 0),
        stats.get("edges", 0),
        stats.get("cyclomatic_complexity", 0),
        stats.get("branch_ratio", 0) * 10,
    ]


def unit(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)


class BaselineIndex:
    """Candidate-only TF-IDF fit. No function name, address, or build label is a feature."""

    def __init__(self, functions: list[FunctionAnalysis]):
        if not functions:
            raise ReconError("EMPTY_INDEX", "No candidate functions to compare.")
        self.functions = functions
        self.opcodes = sorted({i.mnemonic for f in functions for i in f.instructions})
        self.opcode_vectors = self.encode_opcodes(functions)
        self.structures = np.log1p(np.asarray([structure(f) for f in functions], dtype=np.float32))
        self.tfidf = TfidfVectorizer(
            token_pattern=r"\S+",
            lowercase=False,
            ngram_range=(1, 3),
            max_features=4096,
            dtype=np.float32,
        )
        self.ngram_vectors = self.tfidf.fit_transform([token_document(f) for f in functions])

    def encode_opcodes(self, functions: list[FunctionAnalysis]) -> np.ndarray:
        counts = [Counter(i.mnemonic for i in f.instructions) for f in functions]
        return unit(np.asarray([[c[o] for o in self.opcodes] for c in counts], dtype=np.float32))

    def scores(
        self, query: FunctionAnalysis, method: str
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        opcode = (self.encode_opcodes([query]) @ self.opcode_vectors.T)[0]
        ngram = (self.tfidf.transform([token_document(query)]) @ self.ngram_vectors.T).toarray()[0]
        query_structure = np.log1p(np.asarray(structure(query), dtype=np.float32))
        structural = np.exp(-np.mean(np.abs(self.structures - query_structure), axis=1))
        parts = {
            "opcode": np.clip(opcode, 0, 1),
            "ngram": np.clip(ngram, 0, 1),
            "structure": structural,
        }
        if method == "hybrid":
            score = 0.4 * parts["opcode"] + 0.4 * parts["ngram"] + 0.2 * structural
        elif method in parts:
            score = parts[method]
        else:
            raise ReconError("UNKNOWN_METHOD", "Unsupported baseline similarity method.")
        return np.clip(score, 0, 1), parts

    def manifest(self) -> dict[str, Any]:
        return {
            "feature_schema": FEATURE_SCHEMA,
            "engine": "numpy-exact-baseline-1",
            "function_hashes": [f.bytes_hash for f in self.functions],
            "opcodes": self.opcodes,
            "vocabulary": {word: int(index) for word, index in self.tfidf.vocabulary_.items()},
            "idf": self.tfidf.idf_.tolist(),
            "candidate_count": len(self.functions),
        }

    @classmethod
    def restore(
        cls, functions: list[FunctionAnalysis], manifest: dict[str, Any]
    ) -> "BaselineIndex":
        if (
            manifest.get("feature_schema") != FEATURE_SCHEMA
            or manifest.get("engine") != "numpy-exact-baseline-1"
            or manifest.get("function_hashes") != [f.bytes_hash for f in functions]
        ):
            raise ReconError(
                "INDEX_INCOMPATIBLE",
                "Index schema or candidate hashes changed. Rebuild the index.",
                409,
            )
        obj = cls.__new__(cls)
        obj.functions = functions
        obj.opcodes = manifest["opcodes"]
        obj.opcode_vectors = obj.encode_opcodes(functions)
        obj.structures = np.log1p(np.asarray([structure(f) for f in functions], dtype=np.float32))
        obj.tfidf = TfidfVectorizer(
            token_pattern=r"\S+",
            lowercase=False,
            ngram_range=(1, 3),
            dtype=np.float32,
            vocabulary=manifest["vocabulary"],
        )
        obj.tfidf.idf_ = np.asarray(manifest["idf"], dtype=np.float32)
        obj.ngram_vectors = obj.tfidf.transform([token_document(f) for f in functions])
        return obj
