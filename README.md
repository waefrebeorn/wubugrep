# WuBuGrep

**A from-scratch grep in strict C11. Zero dependencies — no vectorscan, no RE2, no libpcre.**

> Byte-exact with GNU grep: ERE 217/217, BRE 64/64 on the canonical GNU test
> suites. Beats ripgrep on dense matching patterns (2–3×) and uppercase-reject.
> Owns a capability ripgrep structurally lacks: **BRE backreferences** `\1`..`\9`.
> SIMD-accelerated everything: literal gate, fused newline/NUL/literal scan,
> subset-DFA walker with class skip, Teddy-style 2nd-byte filtering.

Licensed under the WaefreBeorn Umbrella License v3.0.

## Why

Nathan Baggs' video *"Why It's So Hard To Write A Fast grep"* ends with his
C++26 + vectorscan tool **losing to ripgrep by 80 ms**. The bar is ripgrep —
and ugrep. WuBuGrep studies their published techniques (Teddy, RE/flex
`simd_nlcount`, reverse-suffix automata) and **reimplements them natively in
C11**. We learn; we do not vendor.

## Build

```bash
cc -O3 -flto -march=native -std=c11 -I. -o wubugrep \
    wubugrep.c wubre.c wubre_compile.c wubre_match.c wubre_simd.c \
    wubre_bre.c wubre_dfa.c wubre_litpref.c
```

or `make` (see Makefile), or the self-tuning PGO script: `sh scripts/build_wubugrep.sh`.

Requires: any x86-64 CPU (AVX2 used when present, scalar fallbacks everywhere),
any POSIX system, any C11 compiler. No third-party libraries.

## Usage

```
wubugrep [options] PATTERN [FILE|DIR ...]
  -i  case-insensitive        -v  invert match        -n  line numbers
  -c  count                   -l  files-with-match    -q  quiet (exit only)
  -w  match whole words       -x  match whole lines
  -E  ERE (extended regex)    -G  BRE (basic regex)   -F  fixed string (default)
  -r  recursive               --include=GLOB  --exclude=GLOB
  -a  treat binary as text    --no-color            -h  help
```

Options before or after the pattern; directory without `-r` errors (exit 2) —
both matching GNU grep.

## Architecture (all layers owned)

```
pattern ──► BRE→ERE translator ──► Thompson NFA ──► Pike VM ──┐
              │                    │                          ├─► parallel mmap scan
              │                    └─► subset-construction DFA┘   (line-aligned chunks,
              │                        + SIMD class-skip walk       one thread each)
              ├─► literal-set extraction (DNF of required literals)
              │        ├─► rarest-literal probe selection
              │        └─► vector-accumulator presence gate (rejects at memory bandwidth)
              └─► fused newline+NUL+literal scan (one 128-byte-block AVX2 pass)
                   + lazy line index (built on first match only)
BRE backreferences \1..\9 ──► separate backtracking matcher (DoS-guarded)
```

## Verification (the proof is differential)

```bash
scripts/gauntlet.sh           # md5 byte-exact sweep vs GNU grep
cd external_tests && python3 run_grep_tests.py --mode ere ere.tests   # 217/217
python3 run_grep_tests.py --mode bre bre.tests                         # 64/64
bash scripts/fuzz_adversarial.sh   # malformed + rare-literal fuzz vs grep
cc -O2 -std=c11 -I. -o wubre_test wubre.c wubre_test.c wubre_compile.c \
   wubre_match.c wubre_simd.c wubre_bre.c wubre_dfa.c wubre_litpref.c && ./wubre_test
```

All green at HEAD. ASan+UBSan clean across engine patterns.

## Benchmarks (28 MB / 1M lines, count mode, best-of-3, warm cache)

| class | WuBuGrep | GNU grep 3.11 | ripgrep 14.1 | ugrep 7.8.4 |
|---|---:|---:|---:|---:|
| dense matching `[a-z]+`, `a+`, `[0-9a-f]+` | **18–33 ms** | 2–3 ms | 59–74 ms | 4–5 ms |
| simple literals `the`, `error` | 13–15 ms | 2–3 ms | 14–17 ms | 4–5 ms |
| uppercase reject `[A-Z]` | **9–10 ms** | 71–73 ms | 45 ms | 27–29 ms |
| alternation/quantifier reject | 12–18 ms | 24–40 ms | **8–9 ms** | 8–10 ms |

Full table, methodology and honesty ledger: [`docs/WUBUGREP_SOTA.md`](docs/WUBUGREP_SOTA.md).
Honest position: behind ugrep overall; beats rg on dense matching and
uppercase-reject; ties rg on literals; loses to rg on some reject rows.

## Repo layout

```
wubugrep.c          CLI (argv0 multi-tool dispatch, parallel scan, emit)
wubre*.c/h          engine: compile/match/simd/dfa/bre/litpref modules
external_tests/     canonical GNU grep suites + differential runner
scripts/            gauntlet, adversarial fuzz, benchmark harness, PGO build
docs/               SOTA analysis, benchmarks, honesty ledger
```

## Integration note (WuBuOS)

This repo is the canonical checkout. The WuBuOS tree symlinks it:
`wubuos/src/tools/wubugrep -> /home/wubu/wubugrep` (same pattern as
`src/compiler -> /home/wubu/wubunos`) — one source of truth, no copies.

## License

WaefreBeorn Umbrella License v3.0 (SPDX: WaefreBeorn-UMV3).
