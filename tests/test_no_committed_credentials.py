import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
BINARY_SUFFIXES = {
    ".db",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".pdf",
    ".sqlite",
    ".webp",
}
# .env is the local secret store and is gitignored; .env.example stays scanned.
SECRET_FILE_NAMES = {".env"}
CREDENTIAL_PATTERNS = (
    # Supabase publishable / secret client keys.
    re.compile(r"sb_publishable_[A-Za-z0-9_-]{20,}"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    # Supabase anon / service_role JWTs.
    re.compile(r"eyJhbGciOi[A-Za-z0-9_-]{20,}"),
)


def _iter_repository_text_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPO_ROOT)
        if any(part in SKIP_DIRECTORIES for part in relative.parts):
            continue
        if any(part.startswith("pytest-cache-files-") for part in relative.parts):
            continue
        if path.name in SECRET_FILE_NAMES or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


def test_repository_contains_no_credentials():
    leaks = []
    for path, text in _iter_repository_text_files():
        for pattern in CREDENTIAL_PATTERNS:
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                leaks.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number} ({match.group(0)[:16]}...)"
                )

    assert not leaks, "Credentials must live in .env, not in the repository:\n" + "\n".join(
        leaks
    )
