from pathlib import Path

import pytest

from glm_ko_tok import fetch
from glm_ko_tok.backend_hf import HFBackend
from glm_ko_tok.backend_tiktoken import TiktokenBackend
from glm_ko_tok.loader import TokenizerNotFoundError, load_model, model_dir
from glm_ko_tok.models import MODELS


def test_load_missing_dir_tells_user_to_fetch(tmp_path: Path):
    with pytest.raises(TokenizerNotFoundError, match=r'fetch --model glm-5[.]3'):
        load_model('glm-5.3', tmp_path / 'nope', tmp_path / 'legacy')


def test_model_dir_prefers_new_layout(tmp_path: Path):
    new = tmp_path / 'tokenizers' / 'glm-5.3'
    new.mkdir(parents=True)
    legacy = tmp_path / 'tokenizer'
    legacy.mkdir()
    assert model_dir(MODELS['glm-5.3'], tmp_path / 'tokenizers', legacy) == new


def test_model_dir_falls_back_to_legacy_for_glm(tmp_path: Path, caplog):
    legacy = tmp_path / 'tokenizer'
    legacy.mkdir()
    with caplog.at_level('INFO'):
        got = model_dir(MODELS['glm-5.3'], tmp_path / 'tokenizers', legacy)
    assert got == legacy
    assert 'legacy' in caplog.text


def test_model_dir_no_legacy_for_other_models(tmp_path: Path):
    legacy = tmp_path / 'tokenizer'
    legacy.mkdir()
    got = model_dir(MODELS['kimi-k3'], tmp_path / 'tokenizers', legacy)
    assert got == tmp_path / 'tokenizers' / 'kimi-k3'


def test_load_model_hf_and_tiktoken(tmp_path: Path):
    import base64

    from tokenizers import Tokenizer, models

    from glm_ko_tok.bytes_map import bytes_to_unicode

    hf_dir = tmp_path / 'glm-5.3'
    hf_dir.mkdir()
    table = bytes_to_unicode()
    Tokenizer(models.BPE(vocab={table[b]: b for b in range(256)}, merges=[])).save(
        str(hf_dir / 'tokenizer.json')
    )
    kimi_dir = tmp_path / 'kimi-k3'
    kimi_dir.mkdir()
    (kimi_dir / 'tiktoken.model').write_text(
        '\n'.join(f'{base64.b64encode(bytes([b])).decode()} {b}' for b in range(256)) + '\n'
    )
    hf = load_model('glm-5.3', tmp_path, tmp_path / 'legacy')
    kimi = load_model('kimi-k3', tmp_path, tmp_path / 'legacy')
    assert isinstance(hf.backend, HFBackend)
    assert isinstance(kimi.backend, TiktokenBackend)
    assert hf.directory == hf_dir
    assert kimi.spec.key == 'kimi-k3'


def test_fetch_downloads_pinned_files_and_reference(tmp_path: Path, monkeypatch):
    calls = []

    def fake_download(repo_id, filename, revision, local_dir):
        calls.append((repo_id, filename, revision, Path(local_dir)))
        return str(Path(local_dir) / filename)

    monkeypatch.setattr(fetch, 'hf_hub_download', fake_download)
    paths = fetch.fetch_model(MODELS['kimi-k3'], tmp_path)
    assert [c[1] for c in calls] == [
        'tiktoken.model',
        'tokenizer_config.json',
        'tokenization_kimi.py',
    ]
    assert all(c[0] == 'moonshotai/Kimi-K3' for c in calls)
    assert all(c[2] == MODELS['kimi-k3'].revision for c in calls)
    assert all(c[3] == tmp_path / 'kimi-k3' for c in calls)
    assert [p.name for p in paths] == [c[1] for c in calls]
