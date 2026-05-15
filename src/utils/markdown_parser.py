import re

_REF_RE = re.compile(r"\[\[([^\]]+)\]\]")

_STRIP_RULES = [
    (re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE), ""),  # headings
    (re.compile(r"\[\[([^\]]+)\]\]"), r"\1"),  # [[refs]] → name
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),  # [text](url) → text
    (re.compile(r"`{3}.*?`{3}", re.DOTALL), " "),  # fenced code blocks
    (re.compile(r"`([^`]+)`"), r"\1"),  # inline code
    (re.compile(r"\*{3}([^*]+)\*{3}"), r"\1"),  # bold+italic
    (re.compile(r"\*{2}([^*]+)\*{2}"), r"\1"),  # bold
    (re.compile(r"\*([^*\n]+)\*"), r"\1"),  # italic
    (re.compile(r"_{3}([^_]+)_{3}"), r"\1"),  # __bold+italic__
    (re.compile(r"_{2}([^_]+)_{2}"), r"\1"),  # __bold__
    (re.compile(r"_([^_\n]+)_"), r"\1"),  # _italic_
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), ""),  # unordered lists
    (re.compile(r"^\s*\d+\.\s+", re.MULTILINE), ""),  # ordered lists
    (re.compile(r"^\s*[-*_]{3,}\s*$", re.MULTILINE), ""),  # horizontal rules
    (re.compile(r"^>\s*", re.MULTILINE), ""),  # blockquotes
]


def extract_references(markdown: str) -> list[str]:
    """Return all [[name]] reference names found in a markdown string."""
    return _REF_RE.findall(markdown)


def strip_markdown(markdown: str) -> str:
    """Remove markdown syntax and return plain text suitable for FTS indexing."""
    text = markdown
    for pattern, repl in _STRIP_RULES:
        text = pattern.sub(repl, text)
    return text.strip()
