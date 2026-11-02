from pathlib import Path

import pytest

from glm_ko_tok import fetch
from glm_ko_tok.loader import TokenizerNotFoundError, load_tokenizer


def test_load_missing_dir_tells_user_to_fetch(tmp_path: Path):
    with pytest.raises(TokenizerNotFoundError, match='glm-ko-tok fetch'):
        load_tokenizer(tmp_path / 'nope')


def test_fetch_downloads_only_two_files(tmp_path: Path, monkeypatch):
    calls = []

    def fake_download(repo_id, filename, local_dir):
        calls.append((repo_id, filename, str(local_dir)))
        return str(Path(local_dir) / filename)

    monkeypatch.setattr(fetch, 'hf_hub_download', fake_download)
    paths = fetch.fetch_tokenizer('a/b', tmp_path)
    assert [c[1] for c in calls] == ['tokenizer.json', 'tokenizer_config.json']
    assert all(c[0] == 'a/b' for c in calls)
    assert [p.name for p in paths] == ['tokenizer.json', 'tokenizer_config.json']
