"""Command line entry point for glm-ko-tok."""

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from glm_ko_tok.coverage import compute_coverage
from glm_ko_tok.fetch import DEFAULT_REPO, fetch_tokenizer
from glm_ko_tok.loader import DEFAULT_DIR, TokenizerNotFoundError, load_tokenizer
from glm_ko_tok.split import Analysis, analyze_text
from glm_ko_tok.textio import read_cases, shorten, write, write_err


def _add_input_args(p: argparse.ArgumentParser) -> None:
    p.add_argument('text', nargs='?', help='text to process')
    p.add_argument('--file', help='read cases from a file')
    p.add_argument('--per-line', action='store_true', help='one case per line, print a table')
    p.add_argument('--dir', default=str(DEFAULT_DIR), help='tokenizer directory')


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog='glm-ko-tok', description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('fetch', help='download tokenizer files')
    p.add_argument('--repo', default=DEFAULT_REPO)
    p.add_argument('--dir', default=str(DEFAULT_DIR))

    p = sub.add_parser('coverage', help='Hangul syllable coverage')
    p.add_argument('--dir', default=str(DEFAULT_DIR))
    p.add_argument('--json', action='store_true')

    p = sub.add_parser('analyze', help='per-token byte split report')
    _add_input_args(p)
    p.add_argument('--json', action='store_true')

    return parser


def collect_inputs(args: argparse.Namespace) -> list[str] | None:
    """Return the input texts, or None if no input was given."""
    if args.file:
        cases = read_cases(args.file)
        if args.per_line:
            return cases
        return [Path(args.file).read_text(encoding='utf-8')]
    if args.text is not None:
        return [args.text]
    return None


def _analysis_table(rows: list[tuple[str, Analysis]]) -> str:
    head = f'{"#":>3} {"tokens":>6} {"syl":>4} {"tok/syl":>7} {"invalid":>7} {"split":>5}  text'
    lines = [head]
    for i, (text, a) in enumerate(rows, 1):
        s = a.summary
        tps = '-' if s.tokens_per_syllable is None else f'{s.tokens_per_syllable:.2f}'
        lines.append(
            f'{i:>3} {s.total_tokens:>6} {s.hangul_syllables:>4} {tps:>7} '
            f'{s.invalid_alone:>7} {s.split_chars:>5}  {shorten(text)}'
        )
    tot = sum(a.summary.total_tokens for _, a in rows)
    syl = sum(a.summary.hangul_syllables for _, a in rows)
    inv = sum(a.summary.invalid_alone for _, a in rows)
    spl = sum(a.summary.split_chars for _, a in rows)
    tps = '-' if not syl else f'{tot / syl:.2f}'
    lines.append(f'{"TOTAL":>3} {tot:>6} {syl:>4} {tps:>7} {inv:>7} {spl:>5}')
    return '\n'.join(lines)


def _cmd_analyze(args: argparse.Namespace) -> int:
    inputs = collect_inputs(args)
    if inputs is None:
        write_err('analyze: give TEXT or --file PATH')
        return 2
    tk = load_tokenizer(args.dir)
    if args.per_line:
        rows = [(t, analyze_text(tk, t)) for t in inputs]
        write(_analysis_table(rows))
        return 0
    result = analyze_text(tk, inputs[0])
    write(result.to_json() if args.json else result.format())
    return 0


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == 'fetch':
        for path in fetch_tokenizer(args.repo, args.dir):
            write(f'{args.repo}: {path}')
        return 0
    if args.command == 'coverage':
        result = compute_coverage(load_tokenizer(args.dir))
        write(result.to_json() if args.json else result.format())
        return 0
    if args.command == 'analyze':
        return _cmd_analyze(args)
    msg = f'unknown command: {args.command}'
    raise SystemExit(msg)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    try:
        return _dispatch(args)
    except TokenizerNotFoundError as e:
        write_err(f'error: {e}')
        return 1
