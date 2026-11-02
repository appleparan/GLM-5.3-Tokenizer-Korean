import unicodedata
from pathlib import Path

from glm_ko_tok.textio import read_cases

SAMPLES = Path(__file__).resolve().parent.parent / 'samples' / 'korean.txt'


def test_samples_load_and_include_nfd():
    cases = read_cases(SAMPLES)
    assert len(cases) >= 30
    assert any(c != unicodedata.normalize('NFC', c) for c in cases)
    assert all(not c.startswith('#') for c in cases)
