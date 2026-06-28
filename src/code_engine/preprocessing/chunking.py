"""Dependency-free text chunking helper for future extraction orchestration."""


def chunk_words(text: str, max_words: int) -> list[str]:
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    words = str(text).split()
    return [" ".join(words[index:index + max_words]) for index in range(0, len(words), max_words)]

