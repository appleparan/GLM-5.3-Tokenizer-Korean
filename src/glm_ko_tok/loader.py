"""Load a tokenizer backend from the local `tokenizers/<key>/` directory."""

import logging
from dataclasses import dataclass
from pathlib import Path

from tokenizers import Tokenizer

from glm_ko_tok.backend_hf import HFBackend
from glm_ko_tok.backend_tiktoken import build_kimi_encoding
from glm_ko_tok.models import MODELS, ModelSpec
from glm_ko_tok.protocols import TokenBackend

logger = logging.getLogger(__name__)

DEFAULT_ROOT = Path('tokenizers')
LEGACY_DIR = Path('tokenizer')
LEGACY_KEY = 'glm-5.3'


class TokenizerNotFoundError(FileNotFoundError):
    """Raised when a model's tokenizer file is not present."""


@dataclass(frozen=True)
class LoadedModel:
    """A model spec with its loaded backend and the directory it came from."""

    spec: ModelSpec
    backend: TokenBackend
    directory: Path


def model_dir(spec: ModelSpec, root: Path, legacy_dir: Path = LEGACY_DIR) -> Path:
    """Return the directory of a model's files.

    The old `tokenizer/` directory is used for GLM-5.3 when `<root>/glm-5.3/` is missing.

    Args:
        spec: Model spec.
        root: Directory that holds one sub directory per model key.
        legacy_dir: Old single-model directory.

    Returns:
        The directory to read from.
    """
    target = root / spec.key
    if spec.key == LEGACY_KEY and not target.exists() and legacy_dir.is_dir():
        logger.info('Using legacy tokenizer directory %s for %s', legacy_dir, spec.key)
        return legacy_dir
    return target


def load_model(
    key: str, root: Path | str = DEFAULT_ROOT, legacy_dir: Path | str = LEGACY_DIR
) -> LoadedModel:
    """Load one model's backend.

    Args:
        key: Registry key.
        root: Directory that holds one sub directory per model key.
        legacy_dir: Old single-model directory (GLM-5.3 only).

    Returns:
        The loaded model.

    Raises:
        TokenizerNotFoundError: If the tokenizer file is missing.
    """
    spec = MODELS[key]
    directory = model_dir(spec, Path(root), Path(legacy_dir))
    path = directory / spec.files[0]
    if not path.is_file():
        msg = f'{path} not found. Run `glm-ko-tok fetch --model {key}` to download it.'
        raise TokenizerNotFoundError(msg)
    backend: TokenBackend
    if spec.kind == 'hf':
        backend = HFBackend(Tokenizer.from_file(str(path)))
    else:
        backend = build_kimi_encoding(path)
    return LoadedModel(spec=spec, backend=backend, directory=directory)
