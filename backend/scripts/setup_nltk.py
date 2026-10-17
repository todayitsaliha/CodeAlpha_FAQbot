"""Download the NLTK data packages required by the preprocessing pipeline."""

import sys

import nltk

REQUIRED_PACKAGES = ("punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4")


def main() -> int:
    failed = [pkg for pkg in REQUIRED_PACKAGES if not nltk.download(pkg, quiet=True)]
    if failed:
        print(
            f"ERROR: could not download NLTK packages: {', '.join(failed)}",
            file=sys.stderr,
        )
        return 1
    print("NLTK data ready: " + ", ".join(REQUIRED_PACKAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
