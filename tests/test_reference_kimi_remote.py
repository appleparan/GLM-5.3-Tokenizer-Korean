"""Check our tiktoken backend against Kimi's own tokenizer code.

This test downloads and RUNS `tokenization_kimi.py` from the Hub (`trust_remote_code=True`).
It is skipped by default. Run it only after you have read that file:

    RUN_REMOTE_CODE=1 uv run --group verify pytest -m remote_code
"""

import importlib.util
import os

import pytest

from glm_ko_tok.models import MODELS

pytestmark = [
    pytest.mark.remote_code,
    pytest.mark.skipif(os.environ.get('RUN_REMOTE_CODE') != '1', reason='set RUN_REMOTE_CODE=1'),
    pytest.mark.skipif(
        importlib.util.find_spec('transformers') is None, reason='transformers not installed'
    ),
]


def test_kimi_backend_ids_equal_remote_tokenizer(load_real, sample_lines):
    from transformers import AutoTokenizer

    spec = MODELS['kimi-k3']
    reference = AutoTokenizer.from_pretrained(
        spec.repo, revision=spec.revision, trust_remote_code=True
    )
    assert reference is not None
    backend = load_real('kimi-k3').backend
    for line in sample_lines:
        expected = reference.encode(line, add_special_tokens=False)
        assert backend.encode(line) == expected, line
