import dataclasses

import pytest

from glm_ko_tok.models import MODELS, ModelSpec, resolve_keys


def test_registry_has_three_pinned_models():
    assert list(MODELS) == ['glm-5.3', 'deepseek-v4.1-flash', 'kimi-k3']
    assert MODELS['glm-5.3'].revision == 'ba32f8c19c8738e2c57c71798c601d477a7bf844'
    assert MODELS['deepseek-v4.1-flash'].revision == '314113f8a7dadb388215396ba5fbee2c610a04d6'
    assert MODELS['kimi-k3'].revision == 'f831ab66814297da540d832a5235f8e904f29d06'
    assert all(len(m.revision) == 40 for m in MODELS.values())


def test_kinds_and_files():
    assert MODELS['glm-5.3'].kind == 'hf'
    assert MODELS['deepseek-v4.1-flash'].kind == 'hf'
    kimi = MODELS['kimi-k3']
    assert kimi.kind == 'tiktoken'
    assert 'tiktoken.model' in kimi.files
    assert 'tokenization_kimi.py' in kimi.reference_files
    assert 'tokenization_kimi.py' not in kimi.files


def test_spec_is_frozen_and_has_url():
    spec = MODELS['kimi-k3']
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(spec, 'key', 'x')  # noqa: B010
    assert isinstance(spec, ModelSpec)
    assert spec.revision in spec.url


def test_resolve_keys_default_all_dedupe():
    assert resolve_keys(None) == ['glm-5.3']
    assert resolve_keys([]) == ['glm-5.3']
    assert resolve_keys(['all']) == list(MODELS)
    assert resolve_keys(['kimi-k3', 'glm-5.3', 'kimi-k3']) == ['kimi-k3', 'glm-5.3']


def test_resolve_keys_unknown():
    with pytest.raises(ValueError, match='unknown model'):
        resolve_keys(['nope'])
