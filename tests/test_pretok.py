import json
from pathlib import Path

from glm_ko_tok.backend_tiktoken import KIMI_PAT_STR
from glm_ko_tok.pretok import analyze_patterns, hf_patterns, pretokenizer_info

GLM_PAT = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}{1,3}"
    r'| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+'
)


def test_no_han_no_hangul_for_glm_like_pattern():
    info = analyze_patterns([GLM_PAT])
    assert not info.explicit_han
    assert not info.explicit_hangul


def test_literal_ideograph_range_is_han_and_kana_is_not_hangul():
    info = analyze_patterns(['[一-龥぀-ゟ゠-ヿ]+'])  # noqa: RUF001
    assert info.explicit_han
    assert not info.explicit_hangul


def test_escaped_ranges():
    assert analyze_patterns([r'[\u4e00-\u9fff]']).explicit_han
    assert analyze_patterns([r'[\x{4E00}-\x{9FFF}]']).explicit_han
    assert analyze_patterns([r'[\uac00-\ud7a3]']).explicit_hangul
    assert analyze_patterns([r'[가-힣]+']).explicit_hangul


def test_script_classes():
    assert analyze_patterns([r'[\p{Han}]+']).explicit_han
    assert analyze_patterns([r'\p{Script=Han}']).explicit_han
    assert analyze_patterns([r'\p{Hangul}']).explicit_hangul
    assert not analyze_patterns([r'\p{L}+']).explicit_han


def test_range_outside_cjk_is_ignored():
    info = analyze_patterns([r'[\u0400-\u04ff]', '[à-ÿ]'])
    assert not info.explicit_han
    assert not info.explicit_hangul


def test_kimi_pattern_has_han_class_only():
    info = analyze_patterns([KIMI_PAT_STR])
    assert info.explicit_han
    assert not info.explicit_hangul


def _write(tmp_path: Path, pre_tokenizer: dict | None) -> Path:
    (tmp_path / 'tokenizer.json').write_text(json.dumps({'pre_tokenizer': pre_tokenizer}))
    return tmp_path


def test_hf_patterns_walks_sequences(tmp_path: Path):
    pre = {
        'type': 'Sequence',
        'pretokenizers': [
            {'type': 'Split', 'pattern': {'Regex': r'\p{N}{1,3}'}},
            {'type': 'Split', 'pattern': {'String': ' '}},
            {'type': 'Sequence', 'pretokenizers': [{'type': 'Split', 'pattern': {'Regex': 'x'}}]},
            {'type': 'ByteLevel'},
        ],
    }
    assert hf_patterns(_write(tmp_path, pre) / 'tokenizer.json') == [r'\p{N}{1,3}', 'x']


def test_hf_patterns_handles_missing_pre_tokenizer(tmp_path: Path):
    assert hf_patterns(_write(tmp_path, None) / 'tokenizer.json') == []


def test_pretokenizer_info_by_kind(tmp_path: Path):
    pre = {'type': 'Split', 'pattern': {'Regex': r'[\p{Han}]+'}}
    info = pretokenizer_info('hf', _write(tmp_path, pre))
    assert info is not None
    assert info.explicit_han
    kimi = pretokenizer_info('tiktoken', tmp_path)
    assert kimi is not None
    assert kimi.patterns == [KIMI_PAT_STR]


def test_pretokenizer_info_none_when_file_missing(tmp_path: Path):
    assert pretokenizer_info('hf', tmp_path / 'absent') is None
