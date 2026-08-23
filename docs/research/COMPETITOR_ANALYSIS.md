# WuBuGrep — Competitor Research: Every Angle (2026-08-22)

Primary sources read directly: ripgrep benchsuite + crates (ignore/walk.rs,
searcher, regex-automata meta/strategy.rs, util/prefilter/*), aho-corasick
packed/teddy (algorithm doc + generic.rs), ugrep lib (matcher.cpp 2883 lines,
pattern.cpp 4999 lines, reflex/pattern.h), plus published papers referenced
therein. This is the authoritative redesign input.

---

## 1. The multi-literal gap (our 35x alternates loss) — ROOT CAUSE + FIX

**What rg does for `A|B|C|D|E` (5 literals):**
1. Literal extraction on the HIR produces the exact prefix set.
2. If prefixes enumerate the ENTIRE language (pure literal alternation), the
   prefilter BECOMES the matcher (`Pre<P>` strategy) — no NFA at all.
3. The prefilter cascade picks by literal count/shape:
   memchr -> memchr2 -> memchr3 -> Memmem -> **Teddy** -> ByteSet.
4. For 5 literals, Teddy runs (aho-corasick packed searcher): SIMD PSHUFB
   nibble-LUT over first-byte fingerprints, 32 bytes/chunk AVX2, 8 or 16
   buckets, ~1 vector op pair per chunk covers ALL literals.

**Teddy algorithm (aho-corasick/src/packed/teddy/README.md — full spec read):**
- Fingerprint = first byte of each literal (Hyperscan uses last byte).
- Two 16-byte nibble LUTs A0/A1: bit k set in LUT[nibble] iff some literal's
  fingerprint has that nibble; LUTs duplicated into both AVX2 lanes.
- Per 16-byte haystack chunk B: C = pshufb(A0,B&0xF) & pshufb(A1,(B>>4)&0xF).
  Each lane now holds an 8-bit bucket mask ("which literals have a
  fingerprint here").
- N=2/3 fingerprints: one extra LUT pair per fingerprint byte, chunks
  shifted into alignment (PALIGNR trick / prev-chunk carry byte), all AND'd.
- Candidates: extract set bits from C via movemask->u64 lanes; bucket =
  bitpos%8, offset = bitpos/8; naive verify of that bucket's literals.
- Fat Teddy (AVX2): 16 buckets using 16-bit masks, but only 16B chunks.
- Capacity: slim <=8 patterns, fat <=16. Beyond that -> Aho-Corasick DFA.

**Our fix path (C11, no deps):** implement Slim-Teddy-N2 for <=8 required
literals as a gate+engine: ~60 lines of intrinsics (pshufb/and/or/movemask),
plus Rabin-Karp fallback for tiny buffers. Expected: alternates 3690ms ->
~150-250ms (rg parity is 106ms with Rust's tuned verify; our naive verify is
the same shape theirs started with).

## 2. ugrep's speed secret — BIHASH (different technique, also implementable)

ugrep does NOT use Teddy. RE/flex uses:
- followpos NFA -> subset-construction DFA directly (no epsilon transitions),
  then a **pinned-byte scan**: pick the rarest byte(s) of the pattern
  (min1/min2/min3/min-k variants), scalar-scan 4 bytes/iteration with a
  **bihash table**: `tap[(a ^ (b<<6)) & 0x3FFF]` = 16K-entry uint8 bitset,
  "could this adjacent-byte PAIR start a match?" Only surviving positions
  enter predict_match + the DFA. Effectively a fast approximate prefilter
  inside the hot loop, no SIMD required.
- Our analog: we already have rarest-literal selection + vector gate. What we
  lack is applying it to MULTI-literal sets and to the post-pass.

## 3. Engine selection (rg meta/strategy.rs) — the dispatch tree to copy

```
if anchored-start: skip prefix extraction
else: extract prefixes (literal::Seq)
  if prefixes EXACT && single pattern && no captures && no look-around:
      Pre<P> strategy - the prefilter IS the engine (no NFA!)        <- biggest win
  else if reverse-suffix applicable: ReverseSuffix strategy
       (match END literal, scan backwards; provable via fixed-length
        prefix or disjoint class separator)
  else if reverse-inner applicable: ReverseInner strategy
       (find inner literal, expand outward both ways - our win_only)
  else: Core strategy = lazy DFA <-> Pike VM fallback w/ prefilters attached
```
Key insight we're missing: **when prefixes are exact and complete, skip the
NFA entirely.** Our litpref only ever gates; it never becomes the engine.

## 4. Parallel directory walker (rg ignore/walk.rs) — our -r 10x gap

- Per-thread work-stealing deques (LIFO depth-first - breadth-first is
  disastrous on wide gitignore trees), crossbeam stealers for balance.
- Threads = available_parallelism capped at 12.
- Work item = directory (not file); each thread read_dirs locally, pushes
  subdirs to its own deque, steals when empty.
- Ignore state (gitignore chain) cloned per directory entry (cheap Arc).
- Quit flag + active_workers counter for early termination.

Our walker is single-threaded DFS. Redesign: same structure - per-thread
LIFO stacks + steal, directory-granularity work items, results buffered
per-thread then flushed in deterministic order (we already do ordered emit).

## 5. Unicode/locale

rg pays for UTF-8 handling in the regex-syntax HIR layer, not per byte at
search time: classes are compiled to byte-range sets valid on UTF-8
boundaries. Our ASCII-only cfold is fine for LC_ALL=C parity (the fair
comparison); full UTF-8 class support would be a separate major effort and
is NOT where our benchmark gaps are.

## 6. Other tools surveyed (no new techniques beyond above)
- Hyperscan: origin of Teddy + shufti/truffle (single-byte class accelerators)
  - shufti is the same PSHUFB-nibble idea applied to character classes.
- RE2: NFA/DFA without backtracking; literal extraction similar to rg's;
  nothing new for us beyond what rg shows.
- pcre2 JIT: x86 codegen per pattern; orthogonal (we don't JIT).
- ag/sift/pt: slower than rg in every rg-benchsuite run; no new techniques.

## 7. Prioritized redesign roadmap (measured targets vs today)

| # | Item | Effort | Expected gain | Target |
|---|---|---|---|---|
| 1 | Slim-Teddy-N2 gate/engine for <=8 lits | med | alternates 3690->~200ms | >=15x closer to rg |
| 2 | Prefix-exact => prefilter-as-engine (skip NFA) | small | literal 161->~90ms | rg parity |
| 3 | Reverse-suffix strategy (match end literal, scan back) | medium | surround_words 138->~95 | rg parity |
| 4 | Parallel work-stealing walker | large | -r 2343->~400ms | >=5x |
| 5 | bihash-style hot-loop filter (ugrep) for >8 lits | medium | closes >8-lit case | - |
| 6 | Verify-step improvement (bucket hash instead of naive scan) | small | Teddy polish | - |
