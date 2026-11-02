"""Load a `tokenizers.Tokenizer` from a local directory."""

from pathlib import Path

from tokenizers import Tokenizer

DEFAULT_DIR = Path('tokenizer')


class TokenizerNotFoundError(FileNotFoundError):
    """Raised when tokenizer.json is not present in the directory."""


def load_tokenizer(directory: Path | str = DEFAULT_DIR) -> Tokenizer:
    """Load tokenizer.json from a directory.

    Args:
        directory: Directory that holds tokenizer.json.

    Returns:
        The loaded tokenizer.

    Raises:
        TokenizerNotFoundError: If tokenizer.json is missing.
    """
    path = Path(directory) / 'tokenizer.json'
    if not path.is_file():
        msg = f'{path} not found. Run `glm-ko-tok fetch` to download it.'
        raise TokenizerNotFoundError(msg)
    return Tokenizer.from_file(str(path))
