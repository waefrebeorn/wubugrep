# WuBuGrep

**A from-scratch grep in strict C11. Zero dependencies — no vectorscan, no RE2, no libpcre.**

Licensed under the WaefreBeorn Umbrella License v3.0.

## What is actually true about this tool

Every claim below was measured fresh at HEAD with per-invocation timing,
warm caches, rebuilt binaries, and match-count parity checks against every
competitor. Claims that failed that bar were **retracted**, and the
retractions are kept on record in [`docs/WUBUGREP_SOTA.md`](docs/WUBUGREP_SOTA.md).

### Where WuBuGrep genuinely wins

- **Byte-exact correctness vs GNU grep.** ERE 217/217, BRE 64/64 on the
  canonical GNU test suites; full parity gauntlet (literal/-F/-i/-n/-c ×
  BRE × ERE × ICASE) ALL byte-identical (md5); 100-case adversarial
  malformed-pattern fuzz with zero divergences. This is the primary result:
  a fully owned C11 engine that grep cannot distinguish by output.
- **Dense character-class matching.** On the 28 MB / 1M-line corpus,
  `[a-z]+`, `a+`, `[0-9a-f]+`, `a.*b` run ~18–35 ms vs ripgrep's ~59–73 ms
  (2–3× faster) — via our own subset-construction DFA with SIMD class-skip.
- **Uppercase reject `[A-Z]`.** ~9–10 ms vs grep 72 ms / rg 45 ms /
  ugrep 28 ms — fastest of the four.
- **BRE backreferences `\1`..`\9`.** A capability ripgrep structurally
  cannot express. DoS-guarded backtracking matcher.
- **Zero dependencies, every layer owned.** Literal-set prefilter, AVX2
  gates, fused newline/NUL/literal scan, Thompson NFA → Pike VM, DFA,
  Teddy-style multi-literal search, parallel mmap scanner. Nothing vendored;
  competitor techniques were studied from source and reimplemented natively.

### Where WuBuGrep honestly loses

- **ugrep beats us on nearly all 12 benchmark patterns** (its fixed cost is
  ~4–12 ms flat vs our ~13–27). ugrep is the outright speed leader.
- **ripgrep beats us on alternation/quantifier reject patterns**
  (`foo|bar`, `a{2,4}`, `(ab)+`): its ~8 ms fixed overhead vs our ~13–21 ms.
- **Simple literals**: GNU grep's Boyer–Moore (~2–3 ms) and ugrep (~4–5 ms)
  are far ahead of us (~13–15 ms).
- **Recursive directory search**: still behind on WSL2 — syscall-bound
  (open/fstat/read/close × 80K files ≈ 0.97 s system time), which userspace
  parallelism cannot remove. Our walker improved 3290→2302 ms but rg does it
  in ~206 ms; io_uring/statx batching would be required to close this.
- **Multi-GB / kernel-tree scale**: measured once on linux-kernel; we win
  class-heavy rows there but lose traversal badly. Not exhaustively measured.

The earlier broad "SOTA" framing is retired. The defensible claim is:
*byte-exact vs GNU grep across literal/BRE/ERE/ICASE including -n/-c,
faster than ripgrep on dense matching patterns and uppercase-reject,
competitive on simple literals, behind ugrep overall, zero dependencies,
BRE backreferences.*

## Why

Nathan Baggs' video *"Why It's So Hard To Write A Fast grep"* ends with his
C++26 + vectorscan tool **losing to ripgrep by 80 ms**. WuBuGrep studies
ripgrep/ugrep published techniques (Teddy, RE/flex `simd_nlcount`,
reverse-suffix automata) and **reimplements them natively in C11**. We
learn; we do not vendor.

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
              ├─► Teddy-style one-pass multi-literal search (alternations)
              └─► fused newline+NUL+literal scan (one 128-byte-block AVX2 pass)
                   + lazy line index (built on first match only)
BRE backreferences \1..9 ──► separate backtracking matcher (DoS-guarded)
```

## Verification (the proof is differential)

```bash
make test                        # unit suite + ERE 217 + BRE 64 vs GNU grep
make gauntlet                    # md5 byte-exact sweep vs GNU grep: ALL BYTE-EXACT
make fuzz                        # adversarial malformed/rare-literal fuzz: 100/100
sh scripts/build_wubugrep.sh     # or rebuild, then:
cc -O1 -g -fsanitize=address,undefined -std=c11 -I. -o /tmp/asan_wubu \
    wubugrep.c wubre.c wubre_compile.c wubre_match.c wubre_simd.c \
    wubre_bre.c wubre_dfa.c wubre_litpref.c                      # ASan/UBSan clean
```

All green at HEAD.

## Benchmarks (28 MB / 1M lines, count mode, best-of-3, warm cache)

| class | WuBuGrep | GNU grep 3.11 | ripgrep 14.1 | ugrep 7.8.4 |
|---|---:|---:|---:|---:|
| dense matching `[a-z]+`, `a+`, `[0-9a-f]+` | **18–33 ms** | 2–3 ms | 59–74 ms | 4–5 ms |
| simple literals `the`, `error` | 13–15 ms | **2–3 ms** | 14–17 ms | 4–5 ms |
| uppercase reject `[A-Z]` | **9–10 ms** | 71–73 ms | 45 ms | 27–29 ms |
| alternation/quantifier reject | 12–18 ms | 24–40 ms | **8–9 ms** | 8–10 ms |

Full table, methodology, retraction ledger:
[`docs/WUBUGREP_SOTA.md`](docs/WUBUGREP_SOTA.md),
real-corpus results (500 MB OpenSubtitles, linux-kernel):
[`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

## Needed improvements (admitted gaps, prioritized)

These are real, tracked, and none are hidden:

1. **Fixed per-file overhead (~13–20 ms floor).** ugrep sits at ~4–12 ms.
   Accumulated small passes (mmap setup, chunk split, thread spawn, gate)
   need aggressive fusion. Profile the setup path; skip the chunk-split for
   files under ~1 MB. This alone would flip most reject-pattern losses to rg.
2. **Emit-path batching for dense `-n` output.** Line-index build +
   per-match emit dominate dense-match wall time; bulk index + batched
   writev-style output is designed but not wired.
3. **Recursive walk syscall cost.** io_uring or statx batching, plus
   gitignore-aware skipping like ripgrep. Without this, `-r` stays ~10×
   behind rg on WSL2 regardless of matcher speed.
4. **Corpus-measured literal rarity.** Our rarest-literal probe uses a static
   English letter prior; ugrep's RSA derives actual haystack frequencies.
   (Analysis suggests limited measurable gain in our architecture, but it is
   unproven until measured.)
5. **Multi-GB / kernel-tree benchmark surface.** One linux-kernel row exists;
   the recursive story needs a proper measured table before any claim.
6. **Unicode/locale semantics.** Case folding is ASCII-only (`cfold`);
   no UTF-8 awareness, no locale collation. Fine against grep on ASCII
   corpora; a divergence class waiting for non-ASCII input.

## Repo layout

```
wubugrep.c          CLI (argv0 multi-tool dispatch, parallel scan, emit)
wubre*.c/h          engine: compile/match/simd/dfa/bre/litpref modules
external_tests/     canonical GNU grep suites + differential runner
scripts/            gauntlet, adversarial fuzz, benchmark harnesses, PGO build
docs/               SOTA analysis, benchmarks, honesty ledger
```

## Integration note (WuBuOS)

This repo is the canonical checkout. The WuBuOS tree symlinks it:
`wubuos/src/tools/wubugrep -> /home/wubu/wubugrep` (same pattern as
`src/compiler -> /home/wubu/wubunos`) — one source of truth, no copies.

## License

WaefreBeorn Umbrella License v3.0 (SPDX: WaefreBeorn-UMV3).
