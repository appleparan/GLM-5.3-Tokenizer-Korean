"""Registry of the models this tool can analyze (pinned Hub revisions)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

DEFAULT_KEY = 'glm-5.3'
ALL = 'all'


class UnknownModelError(ValueError):
    """Raised when a model key is not in the registry."""


@dataclass(frozen=True)
class ModelSpec:
    """One model: where its tokenizer comes from and how to load it.

    Attributes:
        key: Short name used on the command line and as the directory name.
        repo: Hugging Face repo id.
        revision: Pinned commit hash of the repo.
        files: Tokenizer files to download and load.
        kind: Backend kind: `hf` (tokenizers JSON) or `tiktoken`.
        reference_files: Files downloaded as reference data only; never executed.
    """

    key: str
    repo: str
    revision: str
    files: tuple[str, ...]
    kind: Literal['hf', 'tiktoken']
    reference_files: tuple[str, ...] = ()

    @property
    def url(self) -> str:
        """Hub URL of the repo tree at the pinned revision."""
        return f'https://huggingface.co/{self.repo}/tree/{self.revision}'


MODELS: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in (
        ModelSpec(
            key='glm-5.3',
            repo='zai-org/GLM-5.3',
            revision='ba32f8c19c8738e2c57c71798c601d477a7bf844',
            files=('tokenizer.json', 'tokenizer_config.json'),
            kind='hf',
        ),
        ModelSpec(
            key='deepseek-v4.1-flash',
            repo='deepseek-ai/DeepSeek-V4.1-Flash',
            revision='314113f8a7dadb388215396ba5fbee2c610a04d6',
            files=('tokenizer.json', 'tokenizer_config.json'),
            kind='hf',
        ),
        ModelSpec(
            key='kimi-k3',
            repo='moonshotai/Kimi-K3',
            revision='f831ab66814297da540d832a5235f8e904f29d06',
            files=('tiktoken.model', 'tokenizer_config.json'),
            kind='tiktoken',
            reference_files=('tokenization_kimi.py',),
        ),
    )
}


def resolve_keys(requested: Sequence[str] | None) -> list[str]:
    """Turn `--model` values into a list of unique model keys.

    Args:
        requested: Keys given on the command line; may contain `all`. Empty means default.

    Returns:
        Model keys in first-seen order.

    Raises:
        UnknownModelError: If a key is not in the registry.
    """
    if not requested:
        return [DEFAULT_KEY]
    keys: list[str] = []
    for key in requested:
        for k in MODELS if key == ALL else [key]:
            if k not in MODELS:
                msg = f'unknown model: {k!r} (choose from {", ".join(MODELS)} or {ALL})'
                raise UnknownModelError(msg)
            if k not in keys:
                keys.append(k)
    return keys
