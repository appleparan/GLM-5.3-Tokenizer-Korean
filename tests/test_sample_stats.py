from pathlib import Path

import pytest

from glm_ko_tok.sample_stats import (
    SampleFormatError,
    korean_stats,
    parallel_stats,
    read_parallel_pairs,
)


def test_korean_stats_counts_tokens_chars_and_fffd(fake_tk):
    stats = korean_stats(fake_tk, ['한a', '국'])
    # 한 -> ed, 95 9c ; a -> 1 ; 국 -> 1 token
    assert stats.lines == 2
    assert stats.total_tokens == 4
    assert stats.chars == 3
    assert stats.tokens_per_char == pytest.approx(4 / 3)
    assert stats.naive_fffd == 3


def test_korean_stats_ignores_spaces_in_char_count(fake_tk):
    assert korean_stats(fake_tk, ['a b']).chars == 2


def test_korean_stats_empty(fake_tk):
    stats = korean_stats(fake_tk, [])
    assert stats.total_tokens == 0
    assert stats.tokens_per_char == 0.0


def test_read_parallel_pairs(tmp_path: Path):
    f = tmp_path / 'p.txt'
    f.write_text('# c\n한\t国\n\nab\tcd\n', encoding='utf-8')
    assert read_parallel_pairs(f) == [('한', '国'), ('ab', 'cd')]


def test_read_parallel_pairs_rejects_bad_line(tmp_path: Path):
    f = tmp_path / 'p.txt'
    f.write_text('only one column\n', encoding='utf-8')
    with pytest.raises(SampleFormatError, match='must be'):
        read_parallel_pairs(f)


def test_parallel_stats(fake_tk):
    stats = parallel_stats(fake_tk, [('국', 'ab'), ('국a', 'ab')])
    assert stats.pairs == 2
    assert stats.ko_tokens == 3
    assert stats.ko_chars == 3
    assert stats.zh_tokens == 2
    assert stats.zh_chars == 4
    assert stats.ko_tokens_per_char == pytest.approx(1.0)
    assert stats.zh_tokens_per_char == pytest.approx(0.5)
    assert len(stats.per_pair) == 2
    assert stats.per_pair[0].ko_tokens == 1
