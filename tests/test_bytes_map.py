import pytest

from glm_ko_tok.bytes_map import bytes_to_unicode, token_bytes, unicode_to_bytes


def test_table_covers_all_bytes_uniquely():
    table = bytes_to_unicode()
    assert sorted(table) == list(range(256))
    assert len(set(table.values())) == 256


def test_printable_ascii_maps_to_itself():
    table = bytes_to_unicode()
    assert table[ord('A')] == 'A'


def test_space_maps_to_g_with_dot():
    assert bytes_to_unicode()[0x20] == 'Ġ'


def test_inverse_table():
    inv = unicode_to_bytes()
    assert inv['Ġ'] == 0x20
    assert len(inv) == 256


def test_token_bytes_roundtrip_hangul():
    table = bytes_to_unicode()
    token = ''.join(table[b] for b in '한'.encode())
    assert token_bytes(token) == '한'.encode()


def test_token_bytes_rejects_foreign_char():
    with pytest.raises(ValueError, match='not a byte-level'):
        token_bytes('한')
