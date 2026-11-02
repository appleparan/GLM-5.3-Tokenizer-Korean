"""Download tokenizer files from the Hugging Face Hub at a pinned revision."""

import logging
from pathlib import Path

from huggingface_hub import hf_hub_download

from glm_ko_tok.models import ModelSpec

logger = logging.getLogger(__name__)


def fetch_model(spec: ModelSpec, root: Path | str) -> list[Path]:
    """Download only the tokenizer files of one model into `<root>/<key>/`.

    Reference files (such as `tokenization_kimi.py`) are saved as data only. This tool never
    imports or runs them.

    Args:
        spec: Model to fetch.
        root: Directory that holds one sub directory per model key.

    Returns:
        Paths of the downloaded files.
    """
    target = Path(root) / spec.key
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in (*spec.files, *spec.reference_files):
        logger.info('Downloading %s from %s@%s', name, spec.repo, spec.revision)
        paths.append(
            Path(
                hf_hub_download(
                    repo_id=spec.repo, filename=name, revision=spec.revision, local_dir=target
                )
            )
        )
    return paths
