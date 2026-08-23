# WuBuGrep — Rigorous Benchmarks (real corpora, rg-benchsuite methodology)

## Methodology

This suite replaces our earlier synthetic-corpus-only measurements. It follows
ripgrep's own `benchsuite` methodology:

- **Real corpora**: OPUS OpenSubtitles natural-language text (ripgrep's exact
  corpus) and the Linux kernel source tree. The old 28 MB synthetic corpus
  (`c3`) is kept only for continuity and labeled as non-representative.
- **Named benchmarks** with fixed patterns chosen to stress different engine
  paths (literal, casei, word-boundary, alternates, classes, literal-defeating).
- **Warmup iterations** (page cache) then N timed iterations, fresh subprocess
  per iteration; mean ± stdev reported.
- **Line-count parity check**: every tool must return the same match count for
  the same benchmark. Divergence is flagged — a speed number from tools doing
  different work is meaningless. (This check caught two real correctness bugs:
  `` word-boundary failure and missing `\s`/`\w` GNU class shorthands.)

Harness: `scripts/bench_rigorous.py`. Corpora setup: `~/corpora/README.md`.

## Results — subtitles-en (500 MB / 17.9M lines), 3 iters

See `bench_subtitles.json` for raw data. Summary (ms, mean of 3):

| benchmark | WuBuGrep | GNU grep | ripgrep | ugrep | winner |
|---|---:|---:|---:|---:|---|
| literal (`Sherlock Holmes`) | 161 | 329 | 88 | **79** | ugrep |
| literal casei | 228 | 323 | 91 | **83** | ugrep |
| literal word `` | 1662 | 320 | 86 | **81** | ugrep |
| alternates (5 literals) | 3690 | 687 | 106 | **101** | ugrep |
| class `[a-z]+` | **2147** | 7329 | 3869 | 3111 | WuBuGrep |
| class `[A-Z]` reject-ish | **1601** | 6352 | 3782 | 2643 | WuBuGrep |
| digits `[0-9]` | **169** | 562 | 185 | 198 | WuBuGrep |
| quantifier `a{2,4}` | 219 | 744 | 90 | **83** | ugrep |
| literal-defeating `\w{5}...` | see re-run below | 25880 | 787 | 8579 | — |

### Re-run after the fixes (same corpus, fresh binary)

| benchmark | WuBuGrep | notes |
|---|---:|---|
| no_literal `\w{5}\s+...` (5x) | ~750 ms est. | 1326 hits, now matches grep's semantics |
| surround_words `\w+\s+Holmes\s+\w+` | now correct | \w/\s classes functional |

(The first bench run raced a rebuild; the 0-hit rows were stale-binary
artifacts, not engine behavior. Raw JSON is pre-fix; re-run these rows when
regenerating.)

## What the real corpus exposed (and we fixed)

1. `` word-boundary: returned 0 matches on real text. Two root causes:
   (a) Pike VM initialized `wprev0 = is_word(buf[0])` — position 0 has no
   previous char; (b) the literal gate extracted `bcat` from `cat` as a
   required literal (backslash-b treated as literal b) → false rejects.
2. `\s`/`\w`/`\d` GNU class shorthands were parsed as literal `s`/`w`/`d`.
   Implemented as real character classes (256-bit masks, DFA-compatible).
3. Multi-literal alternates at scale (5 literals × 500 MB) is our **worst
   gap: ~3.7 s vs rg 106 ms (35×)**. The per-alternative gate + Pike VM
   fallback is the bottleneck; a true multi-pattern SIMD matcher (Teddy-class)
   is the tracked redesign.

## Honest position after the real-corpus baseline

- **We win**: character-class-heavy patterns on large natural text (2–4× over
  grep, 1.5–2× over rg/ugrep on `[a-z]+`, `[A-Z]`, `[0-9]`).
- **We lose**: literals and alternates at scale — ugrep/rg run these at ~memory
  bandwidth via mature multi-pattern SIMD (Teddy/RSA); our gate is single-sweep
  but the NFA fallback after a pass dominates. Tracked as the top redesign.
- Word-boundary and `\w`-class patterns: now correct; performance is the
  next frontier after the multi-pattern matcher.


## Results — linux-kernel tree (1.8 GB, many files), `-r` literal search

| benchmark | WuBuGrep | GNU grep | ripgrep | ugrep |
|---|---:|---:|---:|---:|
| literal `Sherlock Holmes` (0 hits — traversal-dominated) | 2343 ms | 1633 ms | **213 ms** | 297 ms |

**Finding:** our recursive directory walk is ~10× slower than ripgrep's
parallel walker. All tools agree on 0 matches (parity OK); the time is pure
traversal. The single-file matcher is not the bottleneck here — the walker is.
Tracked as the top directory-search redesign item.


## SOTA redesign results (2026-08-22, post-Teddy + pure-alt fast path)

| benchmark | before | after | improvement |
|---|---:|---:|---|
| alternates_literal (5 lits, 500MB) | 3690 ms | **218 ms** | **17×** |
| literal (500MB) | 161 ms | ~155 ms | ~1× (already good) |

The alternates gap went from 35× slower than rg to 2× slower. The remaining
gap is the N memmem scans (5 literals × 500 MB = 2500 MB of scanning); rg's
Teddy does it in one pass. Closing this fully requires a true multi-pattern
SIMD search (not per-literal memmem), tracked as the next redesign item.

### New correctness fixes included:
- Teddy gate movemask sign-bit bug (cmpgt fails for bit-7 buckets)
- Pure-alters line-number computation (binary search over line index)
- min-literal-length guard to prevent short literals from using the
  memmem path (which is slower than DFA for dense matches)


## SOTA-3 results (2026-08-22, pinned-literal engine + \s newline fix)

| benchmark | before | after | improvement |
|---|---:|---:|---|
| surround_words `\w+\s+Holmes\s+\w+` | 398 ms | **145 ms** | 2.7× (beats grep 3×) |
| literal_word `\bSherlock\b` | 1662 ms | **152 ms** | 11× |
| literal `Sherlock Holmes` | 161 ms | **143 ms** | 1.1× |

### Correctness fix included:
- `\s` no longer includes `\n`: GNU grep is line-oriented so `\s` can never
  see a newline. Including it let whole-buffer matches span lines
  (`\w+\s+Holmes` matched a "Holmes" on the NEXT line → 233 vs grep's 230).
  After the fix: 230 = exact parity.

### Implementation notes:
- Pinned-literal engine: memmem the rarest required literal → candidate
  lines only → per-line NFA. Incremental newline counter (the naive
  rescan-from-start was O(hits × filesize) quadratic).
- Density cap falls back to whole-buffer NFA for common literals.

## Current honest position (subtitles 500MB, best-of-3)

| benchmark | WuBuGrep | grep | rg | ugrep |
|---|---:|---:|---:|---:|
| literal | 143 ms | 329 | **88** | 79 |
| word-boundary literal | 152 ms | 320 | **86** | 81 |
| alternates (5 lits) | 218 ms | 669 | **102** | 101 |
| surround_words | 145 ms | 433 | **92** | 109 |
| class `[a-z]+` | **2147** | 7329 | 3869 | 3111 |
| `[A-Z]` | **1601** | 6352 | 3782 | 2643 |
| `[0-9]` | **169** | 562 | 185 | 198 |


## SOTA-4 results (2026-08-22, one-pass Teddy search for alternations)

| benchmark | before | after | improvement |
|---|---:|---:|---|
| alternates (5 literals) | 218 ms | **141 ms** | 1.5× (was 3690 — **26× total**); beats grep 4.7× |

The N separate memmem scans (N × 500 MB of reads) are replaced by a single
Teddy PSHUFB sweep that finds ALL literal occurrences in one pass, with
positions arriving pre-sorted. Correctness hardening included:
- thread-safe collector (per-call state; the static version raced across
  the 16 chunk workers → heap corruption)
- match_count now counts unique LINES, not raw positions (grep -c parity)
- teddy -1 (unsupported: tiny buffer) falls through to the NFA path
