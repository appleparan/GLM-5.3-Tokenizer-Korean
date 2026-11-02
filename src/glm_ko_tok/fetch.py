"""Download the tokenizer files from the Hugging Face Hub."""

import logging
from pathlib import Path

from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

DEFAULT_REPO = 'zai-org/GLM-5.3'
FILES = ('tokenizer.json', 'tokenizer_config.json')


def fetch_tokenizer(repo: str = DEFAULT_REPO, directory: Path | str = 'tokenizer') -> list[Path]:
    """Download only tokenizer.json and tokenizer_config.json.

    Args:
        repo: Hugging Face repo id.
        directory: Target directory.

    Returns:
        Paths of the downloaded files.
    """
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in FILES:
        logger.info('Downloading %s from %s', name, repo)
        paths.append(Path(hf_hub_download(repo_id=repo, filename=name, local_dir=target)))
    return paths
