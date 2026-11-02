import json
from pathlib import Path

import pytest

from glm_ko_tok import cli
from glm_ko_tok.compare import (
    CompareResult,
    char_sets,
    compare_backend,
    compare_models,
    vocab_composition,
)
from glm_ko_tok.loader import LoadedModel
from glm_ko_tok.models import MODELS


def test_char_set_sizes():
    sets = char_sets()
    assert len(sets['Hangul KS X 1001']) == 2350
    assert len(sets['Hangul all']) == 11172
    assert len(sets['Chinese GB2312 L1']) == 3755
    assert len(sets['Hanja KS X 1001']) == 4888
    assert len(sets['CJK Unified']) == 20992
    assert len(sets['Hangul Compat Jamo']) == 51


def test_vocab_composition_fake(fake_tk):
    v = vocab_composition(fake_tk)
    assert v.with_hangul == 1  # 국
    assert v.with_han == 0
    # 0x80..0xFF single bytes plus the 2-byte piece 95 9c are invalid alone
    assert v.invalid_alone == 128 + 1
    assert v.vocab_size == fake_tk.vocab_size


def test_compare_fake_and_json(fake_tk):
    result = CompareResult([compare_backend('fake', fake_tk)])
    ks = result.models[0].sets[0]
    assert ks.name == 'Hangul KS X 1001'
    assert sum(ks.by_count.values()) == ks.total
    data = json.loads(result.to_json())['fake']
    assert data['vocab']['with_hangul'] == 1
    assert data['vocab']['vocab_size'] == fake_tk.vocab_size
    assert 'one_token_ratio' in result.to_json()
    assert 'GB2312' in result.format()
    assert 'summary' not in result.format()


def test_compare_summary_table_has_models_as_columns(fake_tk):
    result = CompareResult([compare_backend('a', fake_tk), compare_backend('b', fake_tk)])
    text = result.format()
    assert '== a ==' in text
    assert '== b ==' in text
    summary = result.summary_table().splitlines()
    assert summary[0].split() == ['set', 'a', 'b']
    assert summary[1].startswith('Hangul KS X 1001')
    assert summary[1].count('%') == 2


def test_cli_compare(fake_tk, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, 'load_model', lambda key, _r: LoadedModel(MODELS[key], fake_tk, Path('nowhere'))
    )
    assert cli.main(['compare']) == 0
    assert 'Hangul KS X 1001' in capsys.readouterr().out
    assert cli.main(['compare', '--json']) == 0
    assert 'glm-5.3' in json.loads(capsys.readouterr().out)
    assert cli.main(['compare', '--model', 'all']) == 0
    assert 'summary' in capsys.readouterr().out


@pytest.mark.integration
def test_compare_real(real_tk):
    r = compare_backend('glm-5.3', real_tk)
    by = {s.name: s for s in r.sets}
    ks = by['Hangul KS X 1001'].by_count
    assert (ks[1], ks[2], ks[3]) == (263, 1337, 750)
    gb = by['Chinese GB2312 L1'].by_count
    assert (gb[1], gb[2]) == (3483, 272)
    assert (r.vocab.with_hangul, r.vocab.with_han, r.vocab.invalid_alone) == (565, 28642, 1095)


def _fake_models(fake_tk, tmp_path: Path) -> list[LoadedModel]:
    (tmp_path / 'tokenizer.json').write_text(
        json.dumps({'pre_tokenizer': {'type': 'Split', 'pattern': {'Regex': r'\p{N}'}}})
    )
    return [
        LoadedModel(MODELS['glm-5.3'], fake_tk, tmp_path),
        LoadedModel(MODELS['kimi-k3'], fake_tk, tmp_path),
    ]


def test_compare_models_reports_samples_and_pretokenizer(fake_tk, tmp_path: Path):
    ko = tmp_path / 'ko.txt'
    ko.write_text('# c\n한a\n', encoding='utf-8')
    pa = tmp_path / 'pa.txt'
    pa.write_text('국\t국a\n', encoding='utf-8')
    result = compare_models(_fake_models(fake_tk, tmp_path), ko, pa)
    glm, kimi = result.models
    assert glm.korean is not None
    assert glm.parallel is not None
    assert glm.pretokenizer is not None
    assert kimi.pretokenizer is not None
    assert glm.korean.total_tokens == 3
    assert glm.parallel.pairs == 1
    assert glm.pretokenizer.patterns == [r'\p{N}']
    assert not glm.pretokenizer.explicit_han
    assert kimi.pretokenizer.explicit_han
    text = result.format()
    assert 'Korean sample (1 lines)' in text
    assert 'Parallel ko/zh (1 pairs)' in text
    assert 'explicit Han range/class: yes' in text
    assert 'Hangul range: no' in text
    data = json.loads(result.to_json())
    assert data['kimi-k3']['pretokenizer']['explicit_han'] is True
    assert data['glm-5.3']['korean']['naive_fffd'] == 3
    assert data['glm-5.3']['parallel']['per_pair'][0]['ko'] == '국'


def test_compare_models_without_sample_files(fake_tk, tmp_path: Path):
    models = _fake_models(fake_tk, tmp_path)[:1]
    result = compare_models(models, tmp_path / 'no1', tmp_path / 'no2')
    assert result.models[0].korean is None
    assert result.models[0].parallel is None
    assert 'Korean sample' not in result.format()


def test_cli_compare_bad_parallel_file_is_an_error(fake_tk, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli, 'load_model', lambda key, _r: LoadedModel(MODELS[key], fake_tk, tmp_path)
    )
    bad = tmp_path / 'bad.txt'
    bad.write_text('no tab here\n', encoding='utf-8')
    assert cli.main(['compare', '--parallel-file', str(bad)]) == 2
    assert 'must be' in capsys.readouterr().err


def test_format_escapes_control_chars_in_patterns(fake_tk, tmp_path: Path):
    (tmp_path / 'tokenizer.json').write_text(
        json.dumps({'pre_tokenizer': {'type': 'Split', 'pattern': {'Regex': 'a\r\nb'}}})
    )
    model = LoadedModel(MODELS['glm-5.3'], fake_tk, tmp_path)
    text = compare_models([model], None, None).format()
    assert '[1] a\\r\\nb' in text
