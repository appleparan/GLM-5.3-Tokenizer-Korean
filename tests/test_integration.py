import pytest

from glm_ko_tok.coverage import compute_coverage
from glm_ko_tok.split import analyze_text

pytestmark = pytest.mark.integration


def test_naive_decode_breaks_annyeong(real_tk):
    ids = real_tk.encode('안녕하세요', add_special_tokens=False).ids
    naive = ''.join(real_tk.decode([i]) for i in ids)
    assert '�' in naive
    assert real_tk.decode(ids) == '안녕하세요'


def test_analyze_real_marks_invalid_tokens(real_tk):
    res = analyze_text(real_tk, '안녕하세요')
    assert res.summary.invalid_alone >= 2
    assert res.summary.split_chars >= 1


def test_coverage_real_matches_measured_facts(real_tk):
    result = compute_coverage(real_tk)
    assert result.ks.total == 2350
    assert result.ks.single == 263
    assert result.all.single == 263
