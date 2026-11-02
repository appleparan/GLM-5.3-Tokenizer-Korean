import json

import pytest

from glm_ko_tok import cli
from glm_ko_tok.compare import char_sets, compare_tokenizer, vocab_composition


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


def test_compare_fake_and_json(fake_tk):
    result = compare_tokenizer(fake_tk)
    ks = result.sets[0]
    assert ks.name == 'Hangul KS X 1001'
    assert sum(ks.by_count.values()) == ks.total
    assert json.loads(result.to_json())['vocab']['with_hangul'] == 1
    assert 'one_token_ratio' in result.to_json()
    assert 'GB2312' in result.format()


def test_cli_compare(fake_tk, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'load_tokenizer', lambda _d: fake_tk)
    assert cli.main(['compare']) == 0
    assert 'Hangul KS X 1001' in capsys.readouterr().out
    assert cli.main(['compare', '--json']) == 0
    assert 'vocab' in json.loads(capsys.readouterr().out)


@pytest.mark.integration
def test_compare_real(real_tk):
    r = compare_tokenizer(real_tk)
    by = {s.name: s for s in r.sets}
    ks = by['Hangul KS X 1001'].by_count
    assert (ks[1], ks[2], ks[3]) == (263, 1337, 750)
    gb = by['Chinese GB2312 L1'].by_count
    assert (gb[1], gb[2]) == (3483, 272)
    assert (r.vocab.with_hangul, r.vocab.with_han, r.vocab.invalid_alone) == (565, 28642, 1095)
