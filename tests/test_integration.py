import pytest

from glm_ko_tok.coverage import compute_coverage
from glm_ko_tok.split import analyze_text

pytestmark = pytest.mark.integration


def test_naive_decode_breaks_annyeong(real_tk):
    ids = real_tk.encode('안녕하세요')
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


def test_incremental_equals_original_on_real(real_tk):
    from glm_ko_tok.stream_sim import simulate_stream

    report = simulate_stream(real_tk, '안녕하세요')
    by = {r.name: r for r in report.results}
    assert '�' in by['naive'].output
    assert by['incremental'].output == '안녕하세요'
    assert not by['decode_stream'].skipped
    assert by['decode_stream'].equals_truth


@pytest.mark.parametrize('key', ['glm-5.3', 'deepseek-v4.1-flash', 'kimi-k3'])
def test_all_models_roundtrip_samples_and_stream(key, load_real, sample_lines):
    from glm_ko_tok.stream_sim import simulate_stream

    backend = load_real(key).backend
    for line in sample_lines:
        ids = backend.encode(line)
        assert b''.join(backend.token_bytes(i) for i in ids) == line.encode('utf-8')
        assert backend.decode(ids) == line
        by = {r.name: r for r in simulate_stream(backend, line).results}
        assert by['incremental'].equals_truth


def test_real_vocab_sizes(load_real):
    assert load_real('deepseek-v4.1-flash').backend.vocab_size == 129280
    assert load_real('kimi-k3').backend.vocab_size == 163584
