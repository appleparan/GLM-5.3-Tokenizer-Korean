"""Our HF backend must give the same ids as `tokenizers` called directly."""

from pathlib import Path

import pytest

from tokenizers import Tokenizer

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('key', ['glm-5.3', 'deepseek-v4.1-flash'])
def test_backend_ids_equal_tokenizers_ids(key, load_real, sample_lines):
    model = load_real(key)
    reference = Tokenizer.from_file(str(Path(model.directory) / 'tokenizer.json'))
    assert len(sample_lines) > 30
    for line in sample_lines:
        expected = reference.encode(line, add_special_tokens=False).ids
        assert model.backend.encode(line) == expected, line
