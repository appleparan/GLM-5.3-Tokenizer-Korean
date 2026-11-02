import tiktoken
from tokenizers import Tokenizer, decoders, models, pre_tokenizers

from glm_ko_tok.backend_hf import HFBackend
from glm_ko_tok.backend_tiktoken import KIMI_PAT_STR, TiktokenBackend, build_kimi_encoding
from glm_ko_tok.bytes_map import bytes_to_unicode


def _hf_backend() -> HFBackend:
    table = bytes_to_unicode()
    vocab = {table[b]: b for b in range(256)}
    vocab[table[0xED] + table[0x95]] = 256
    tk = Tokenizer(models.BPE(vocab=vocab, merges=[(table[0xED], table[0x95])]))
    tk.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tk.decoder = decoders.ByteLevel()
    return HFBackend(tk)


def _tt_backend() -> TiktokenBackend:
    ranks = {bytes([b]): b for b in range(256)}
    ranks[b'ab'] = 256
    enc = tiktoken.Encoding(name='t', pat_str=r'\S+|\s+', mergeable_ranks=ranks, special_tokens={})
    return TiktokenBackend(enc)


def test_hf_backend_basics():
    be = _hf_backend()
    ids = be.encode('한a')
    assert ids == [256, 0x9C, 0x61] or len(ids) == 3
    assert b''.join(be.token_bytes(i) for i in ids) == '한a'.encode()
    assert be.decode(ids) == '한a'
    assert be.vocab_size == 257
    vocab_bytes = list(be.iter_vocab_bytes())
    assert len(vocab_bytes) == 257
    assert b'\xed\x95' in vocab_bytes


def test_hf_backend_exposes_tokenizer_for_decode_stream():
    be = _hf_backend()
    assert isinstance(be.tokenizer, Tokenizer)


def test_tiktoken_backend_basics():
    be = _tt_backend()
    assert be.encode('abc') == [256, 0x63]
    assert be.token_bytes(256) == b'ab'
    assert be.decode([256, 0x63]) == 'abc'
    assert be.vocab_size == 257
    assert sorted(be.iter_vocab_bytes(), key=len)[-1] == b'ab'
    assert len(list(be.iter_vocab_bytes())) == 257


def test_tiktoken_decode_single_partial_byte_is_replacement():
    be = _tt_backend()
    assert be.decode([0xED]) == '�'


def test_build_kimi_encoding_from_ranks_file(tmp_path):
    import base64

    path = tmp_path / 'tiktoken.model'
    lines = [f'{base64.b64encode(bytes([b])).decode()} {b}' for b in range(256)]
    lines.append(f'{base64.b64encode("한".encode()).decode()} 256')
    path.write_text('\n'.join(lines) + '\n')
    be = build_kimi_encoding(path)
    assert be.encode('한') == [256]
    assert be.encode('a') == [97]
    assert be.decode([256]) == '한'


def test_kimi_pattern_is_han_aware():
    assert r'\p{Han}' in KIMI_PAT_STR
    assert KIMI_PAT_STR.count('|') >= 7
