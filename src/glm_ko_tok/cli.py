"""Command line entry point for glm-ko-tok."""

import argparse
import json
import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path

from glm_ko_tok import probe
from glm_ko_tok.compare import CompareResult, compare_backend
from glm_ko_tok.coverage import compute_coverage
from glm_ko_tok.fetch import fetch_model
from glm_ko_tok.loader import DEFAULT_ROOT, LoadedModel, TokenizerNotFoundError, load_model
from glm_ko_tok.models import MODELS, UnknownModelError, resolve_keys
from glm_ko_tok.split import Analysis, analyze_text
from glm_ko_tok.stream_sim import StreamReport, simulate_stream
from glm_ko_tok.textio import read_cases, shorten, write, write_err


def _add_model_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        '--model',
        action='append',
        metavar='KEY',
        help=f'model key (repeatable) or "all"; keys: {", ".join(MODELS)} (default glm-5.3)',
    )
    p.add_argument('--root', default=str(DEFAULT_ROOT), help='directory with one folder per model')


def _add_input_args(p: argparse.ArgumentParser) -> None:
    p.add_argument('text', nargs='?', help='text to process')
    p.add_argument('--file', help='read cases from a file')
    p.add_argument('--per-line', action='store_true', help='one case per line, print a table')
    _add_model_args(p)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog='glm-ko-tok', description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('fetch', help='download tokenizer files at the pinned revision')
    _add_model_args(p)

    p = sub.add_parser('coverage', help='Hangul syllable coverage')
    _add_model_args(p)
    p.add_argument('--json', action='store_true')

    p = sub.add_parser('analyze', help='per-token byte split report')
    _add_input_args(p)
    p.add_argument('--json', action='store_true')

    p = sub.add_parser('stream-sim', help='simulate streaming decode')
    _add_input_args(p)
    p.add_argument('--json', action='store_true')

    p = sub.add_parser('compare', help='token cost of Hangul vs Hanja vs Chinese')
    _add_model_args(p)
    p.add_argument('--json', action='store_true')
    _add_probe_parser(sub)
    return parser


def _add_probe_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser('probe', help='probe a streaming OpenAI-compatible endpoint')
    p.add_argument('--target', choices=['vllm', 'openrouter'], default='vllm')
    p.add_argument('--api', choices=['chat', 'responses'], default='chat')
    p.add_argument('--base-url', help='overrides the target preset')
    p.add_argument('--model', required=True)
    p.add_argument('--prompt', required=True)
    p.add_argument('--api-key-env', help='env var holding the API key (overrides preset)')
    p.add_argument('--out', help='JSONL output path, e.g. runs/x.jsonl')
    p.add_argument('--max-tokens', type=int, default=256)
    p.add_argument('--provider', action='append', default=[], help='pin upstream (repeatable)')


def _cmd_probe(args: argparse.Namespace) -> int:
    try:
        config = probe.build_config(
            target=args.target,
            model=args.model,
            prompt=args.prompt,
            env=os.environ,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            api=args.api,
            max_tokens=args.max_tokens,
            providers=args.provider,
        )
        result = probe.run_probe(config, out=args.out)
    except probe.ProbeConfigError as e:
        write_err(f'error: {e}')
        return 2
    except probe.ProbeError as e:
        write_err(f'error: {e}')
        return 1
    write(result.format())
    if args.out:
        write(f'saved: {args.out}')
    return 0


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
    models = _load_models(args)
    if args.per_line:
        _emit(models, lambda m: _analysis_table([(t, analyze_text(m.backend, t)) for t in inputs]))
        return 0
    if args.json:
        _emit_json(models, lambda m: analyze_text(m.backend, inputs[0]).to_json())
    else:
        _emit(models, lambda m: analyze_text(m.backend, inputs[0]).format())
    return 0


def _stream_table(rows: list[StreamReport]) -> str:
    head = (
        f'{"#":>3} {"naive":>6} {"incr":>5} {"dstream":>7} {"naive=":>6} {"incr=":>5} '
        f'{"dstr=":>5}  text'
    )
    lines = [head]
    totals = [0, 0, 0]
    eq = [0, 0, 0]
    for i, rep in enumerate(rows, 1):
        r = rep.results
        ds_ok = not r[2].skipped
        for k in range(3):
            totals[k] += r[k].fffd_count
            eq[k] += int(r[k].equals_truth)
        dsf = r[2].fffd_count if ds_ok else '-'
        lines.append(
            f'{i:>3} {r[0].fffd_count:>6} {r[1].fffd_count:>5} {dsf:>7} '
            f'{int(r[0].equals_truth):>6} {int(r[1].equals_truth):>5} '
            f'{int(r[2].equals_truth) if ds_ok else "-":>5}  {shorten(rep.text)}'
        )
    n = len(rows)
    lines.append(
        f'{"TOTAL":>3} {totals[0]:>6} {totals[1]:>5} {totals[2]:>7} '
        f'{eq[0]}/{n:<4} {eq[1]}/{n:<3} {eq[2]}/{n}'
    )
    return '\n'.join(lines)


def _cmd_stream_sim(args: argparse.Namespace) -> int:
    inputs = collect_inputs(args)
    if inputs is None:
        write_err('stream-sim: give TEXT or --file PATH')
        return 2
    models = _load_models(args)
    if args.per_line:
        _emit(models, lambda m: _stream_table([simulate_stream(m.backend, t) for t in inputs]))
    elif args.json:
        _emit_json(models, lambda m: simulate_stream(m.backend, inputs[0]).to_json())
    else:
        _emit(models, lambda m: simulate_stream(m.backend, inputs[0]).format())
    return 0


def _load_models(args: argparse.Namespace) -> list[LoadedModel]:
    return [load_model(k, args.root) for k in resolve_keys(args.model)]


def _emit(models: list[LoadedModel], render: Callable[[LoadedModel], str]) -> None:
    """Print one report; with several models, a `== key ==` header before each."""
    for m in models:
        write(render(m) if len(models) == 1 else f'== {m.spec.key} ==\n{render(m)}\n')


def _emit_json(models: list[LoadedModel], render: Callable[[LoadedModel], str]) -> None:
    """Print JSON; with several models, an object keyed by model key."""
    if len(models) == 1:
        write(render(models[0]))
        return
    data = {m.spec.key: json.loads(render(m)) for m in models}
    write(json.dumps(data, ensure_ascii=False, indent=2))


def _cmd_fetch(args: argparse.Namespace) -> int:
    for key in resolve_keys(args.model):
        for path in fetch_model(MODELS[key], args.root):
            write(f'{key}: {path}')
    return 0


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == 'fetch':
        return _cmd_fetch(args)
    if args.command == 'coverage':
        models = _load_models(args)
        if args.json:
            _emit_json(models, lambda m: compute_coverage(m.backend).to_json())
        else:
            _emit(models, lambda m: compute_coverage(m.backend).format())
        return 0
    if args.command == 'analyze':
        return _cmd_analyze(args)
    if args.command == 'compare':
        result = CompareResult([compare_backend(m.spec.key, m.backend) for m in _load_models(args)])
        write(result.to_json() if args.json else result.format())
        return 0
    if args.command == 'probe':
        return _cmd_probe(args)
    if args.command == 'stream-sim':
        return _cmd_stream_sim(args)
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
    except UnknownModelError as e:
        write_err(f'error: {e}')
        return 2
    except TokenizerNotFoundError as e:
        write_err(f'error: {e}')
        return 1
