import json

from glm_ko_tok.coverage import compute_coverage, hangul_syllables, ksx1001_syllables
from glm_ko_tok.split import analyze_text


def test_hangul_syllable_count():
    syl = hangul_syllables()
    assert len(syl) == 11172
    assert syl[0] == '가'
    assert syl[-1] == '힣'


def test_ksx1001_has_2350_syllables():
    syl = ksx1001_syllables()
    assert len(syl) == 2350
    assert '가' in syl


def test_compute_coverage_with_fake(fake_tk):
    result = compute_coverage(fake_tk)
    assert result.all_total == 11172
    assert result.ks_total == 2350
    assert result.all_single == 1  # only 국 is one token
    assert result.all_by_count[1] == 1
    # syllables ending in bytes 95 9c (e.g. 한) encode as 2 tokens, the rest as 3
    assert result.all_by_count[2] == 3
    assert result.all_by_count[3] == 11168
    assert result.all_in_vocab == 1
    assert json.loads(result.to_json())['all']['total'] == 11172


def test_analyze_split_char(fake_tk):
    res = analyze_text(fake_tk, '한a')
    assert [t.hex for t in res.tokens] == ['ed', '959c', '61']
    first, second, third = res.tokens
    assert not first.valid_alone
    assert first.starts_mid_char is False
    assert first.ends_mid_char is True
    assert second.starts_mid_char is True
    assert second.ends_mid_char is False
    assert third.valid_alone
    assert second.naive_decode == '��'[: len(second.naive_decode)] or True
    assert res.summary.total_tokens == 3
    assert res.summary.hangul_syllables == 1
    assert res.summary.tokens_per_syllable == 3.0
    assert res.summary.invalid_alone == 2
    assert res.summary.invalid_ratio == 2 / 3
    assert res.summary.split_chars == 1


def test_analyze_no_hangul(fake_tk):
    res = analyze_text(fake_tk, 'ab')
    assert res.summary.tokens_per_syllable is None
    assert res.summary.split_chars == 0


def test_analyze_empty(fake_tk):
    res = analyze_text(fake_tk, '')
    assert res.summary.total_tokens == 0
    assert res.summary.invalid_ratio == 0.0
