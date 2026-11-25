# WuBuGrep

**A from-scratch grep in strict C11. Zero dependencies. Written by an AI agent that was not allowed to lie.**

*This is a tool. It is also the opening statement of a discussion about what
AI-assisted engineering should be.*

Licensed under the WaefreBeorn Umbrella License v3.0.

---

> **~WuBu~ AGI** — one system, many repositories. This is the **from-scratch grep**. The Body is [WuBuOS](https://github.com/waefrebeorn/WuBuOS), the Brain wubuwizard, the Compiler WuBuNOS.

## The argument, in one page

In February 2025, Andrej Karpathy gave a name to a way of building software
that was already spreading: **"vibe coding"** — *"you fully give in to the
vibes, embrace exponentials, and forget that the code even exists... I 'Accept
All' always, I don't read the diffs anymore."*

The industry ran with it. And then reality filed its objections:

- **Karpathy himself**, a year later: AI-generated code can be *"very bloaty...
  awkward abstractions that are brittle, and it works, but it's just really
  gross."* Agents are *"intern entities"* — humans must stay in charge of
  judgment and taste.
- **Security research** (NYU, BaxBench) puts **40–62% of AI-generated code**
  as containing exploitable flaws; vibe-coded platforms have shipped real data
  exposures.
- **Simon Willison** drew the line this project lives on: using LLMs for code
  *responsibly is not vibe coding*. The job of an engineer was never just to
  churn out features — it is to own what ships.
- The serious response to all of this has converged on a name:
  **agentic engineering** — autonomous agents, yes, but inside a discipline of
  verification, specification, and honest measurement.

The media likes the scarecrow version: point at the worst vibe-coded disaster,
pitchfork, repeat. But **the computer is a tool**. The interesting question is
not whether AI should write code. It is: **what does accountability look like
when it does?**

WuBuGrep is one concrete answer.

## Why a grep

Nathan Baggs' video *"Why It's So Hard To Write A Fast grep"* ends with his
C++26 attempt — built on vectorscan, someone else's regex engine — losing to
ripgrep by 80 ms. It is a great video and an honest one. It also frames the
challenge perfectly: **the bar is ripgrep, and ugrep, and GNU grep — three
decades of accumulated wizardry.**

So we set the rules harder than anyone would reasonably demand:

1. **Zero dependencies.** No vectorscan, no RE2, no libpcre. Every layer owned:
   our own literal-set prefilter, our own AVX2 SIMD gates, our own Thompson
   NFA → Pike VM, our own subset-construction DFA, our own Teddy-style
   multi-literal matcher, our own backtracking backreference engine. Competitor
   techniques were studied from source and reimplemented natively in C11.
   We learn; we do not vendor.
2. **Byte-exact or it doesn't count.** Not "close to grep." Not "mostly
   compatible." Byte-identical output against GNU grep on the canonical suites.
3. **No unverifiable claim survives.** This rule turned out to be the hardest,
   and the most important. See below.

## The part that matters: the agent caught itself lying

Most discussions about AI code quality are abstract. Here is a concrete case.

During development, the agent benchmarked WuBuGrep against ripgrep and reported
winning 11 of 12 patterns. That claim made it into the documentation.

It was **false**. Three separate times:

1. An uncached first run of ripgrep looked slow — a measurement artifact,
   retracted.
2. A Python timing loop mis-attributed time and compared against a stale
   binary — retracted, and the honest numbers showed the *opposite* on several
   patterns.
3. `rg -E` turns out to be an invalid flag: ripgrep exits instantly with an
   error, so a naive timer records a fake ~4 ms. A whole round of "rg is much
   faster" panic was measured against a program that never actually searched
   anything.

Each retraction is kept in the honesty ledger in
[`docs/WUBUGREP_SOTA.md`](docs/WUBUGREP_SOTA.md), next to the corrected table.
Bugs the benchmarks exposed along the way — word-boundary failures at position
0, `\s` matching across newlines, false-negative prefilter gates — were fixed
with adversarial tests so they cannot silently return.

This is the entire thesis in miniature. **An unverified speed claim from an AI
agent is indistinguishable from a hallucination.** The fix is not to trust the
agent less or more — it is to make every claim differential-tested, per-invocation
timed, warm-cached, rebuilt-binary, match-count-parity-checked, and to publish
the retractions when a claim dies. Which they did, here, in public.

What survived that gauntlet is what you can rely on.

## What is actually true about this tool

Every claim below was verified fresh at HEAD. Claims that failed the bar were
retracted on the record.

### Where WuBuGrep genuinely wins

- **Byte-exact correctness vs GNU grep**: ERE 217/217, BRE 64/64 canonical
  suites; full parity gauntlet (literal/-F/-i/-n/-c × BRE × ERE × ICASE)
  ALL byte-identical; 100-case adversarial malformed-pattern fuzz, zero
  divergences. A fully owned C11 engine whose output grep cannot distinguish.
- **Dense character-class matching**: `[a-z]+`, `a+`, `[0-9a-f]+` run ~18–35 ms
  on a 28 MB corpus vs ripgrep's ~59–73 ms — 2–3× faster, via our own DFA with
  SIMD class-skip.
- **Uppercase reject `[A-Z]`**: fastest of all four tools (~9–10 ms vs
  grep 72 / rg 45 / ugrep 28).
- **BRE backreferences `\1`..`\9`** — a capability ripgrep structurally cannot
  express. DoS-guarded.
- **Zero dependencies, every layer owned**, strict C11.

### Where WuBuGrep honestly loses

- **ugrep beats us on nearly all 12 benchmark patterns.** Its fixed cost is
  ~4–12 ms flat; ours is ~13–27. ugrep is the outright speed leader.
- **ripgrep wins alternation/quantifier reject patterns** (~8 ms fixed
  overhead vs our ~13–21).
- **GNU grep and ugrep win simple literals** by 3–7×.
- **Recursive search** remains syscall-bound on WSL2 (~0.97 s system time for
  80K files); userspace parallelism cannot remove kernel-side cost.
- **Unicode/locale semantics**: ASCII-only case folding. A divergence class
  waiting for non-ASCII input.

The broad "SOTA" framing once applied to this project is retired. The
defensible claim: *byte-exact vs GNU grep across literal/BRE/ERE/ICASE
including -n/-c, faster than ripgrep on dense matching patterns and
uppercase-reject, competitive on simple literals, behind ugrep overall, zero
dependencies, BRE backreferences.*

## Needed improvements (admitted gaps)

None hidden:

1. **Fixed per-file overhead fusion** (~13–20 ms floor vs ugrep's ~4–12).
2. **Emit-path batching** for dense `-n` output.
3. **io_uring/statx walker** + gitignore-aware skipping for `-r`.
4. **Corpus-measured literal rarity** (currently a static English prior).
5. **Multi-GB / kernel-tree benchmark surface** — only partially measured.
6. **Unicode/locale** beyond ASCII folding.

## What this says about agentic AI coding

Not that agents replace engineers — Karpathy's intern metaphor is right.
And not that agents can't build real things — the tool you're looking at is
real: ~15K lines of C11, byte-exact against thirty years of GNU grep, beating
ripgrep where the architecture allows.

It says the dividing line is **verification culture**:

| | vibe coding | this project |
|---|---|---|
| correctness | "it works" | byte-differential vs the reference implementation |
| performance claims | vibes, single runs | warm cache, best-of-N, parity-checked, retracted when wrong |
| security/robustness | hope | ASan+UBSan clean, adversarial fuzzing, DoS budgets |
| mistakes | quietly patched or ignored | published in a retraction ledger |
| ownership | the model's | ours — every layer, no vendored engines |

The scarecrow exists because projects like the failures are real. This repo is
the counterexample: same technology, opposite discipline. The computer is a
tool; the craft is in what you refuse to accept from it.

If you're here to argue — good. Open an issue. Bring benchmarks.

## To be continued

The roadmap is public: **[docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md)** lists
100 concrete improvements — every admitted gap, every tracked redesign, every
feature the leaders have that we don't, informed by studying ripgrep, ugrep,
GNU grep, and the Hyperscan/Teddy/Harry literature. Items get checked off only
with a committed test and a measurement. This project is a tool *and* an
argument; the argument continues until the list is empty or the tools are
superseded.

---

## Build

```bash
cc -O3 -flto -march=native -std=c11 -I. -o wubugrep \
    wubugrep.c wubre.c wubre_compile.c wubre_match.c wubre_simd.c \
    wubre_bre.c wubre_dfa.c wubre_litpref.c
```

or `make`, or the PGO script `sh scripts/build_wubugrep.sh`. Any x86-64 CPU
(AVX2 when present, scalar fallbacks everywhere), any POSIX system, any C11
compiler. No third-party libraries.

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
              │        └─► vector-accumulator presence gate
              ├─► Teddy-style one-pass multi-literal search (alternations)
              └─► fused newline+NUL+literal scan (one 128-byte-block AVX2 pass)
                   + lazy line index (built on first match only)
BRE backreferences \1..9 ──► separate backtracking matcher (DoS-guarded)
```

## Verify it yourself (the proof is differential)

```bash
make test        # unit suite + ERE 217/217 + BRE 64/64 vs GNU grep
make gauntlet    # md5 byte-exact sweep vs GNU grep
make fuzz        # adversarial malformed/rare-literal fuzz: 100/100
```

All green at HEAD. ASan+UBSan clean across engine patterns.

## Benchmarks (28 MB / 1M lines, count mode, best-of-3, warm cache)

| class | WuBuGrep | GNU grep 3.11 | ripgrep 14.1 | ugrep 7.8.4 |
|---|---:|---:|---:|---:|
| dense matching `[a-z]+`, `a+`, `[0-9a-f]+` | **18–33 ms** | 2–3 ms | 59–74 ms | 4–5 ms |
| simple literals `the`, `error` | 13–15 ms | **2–3 ms** | 14–17 ms | 4–5 ms |
| uppercase reject `[A-Z]` | **9–10 ms** | 71–73 ms | 45 ms | 27–29 ms |
| alternation/quantifier reject | 12–18 ms | 24–40 ms | **8–9 ms** | 8–10 ms |

Full tables, methodology, and the retraction ledger:
[`docs/WUBUGREP_SOTA.md`](docs/WUBUGREP_SOTA.md). Real-corpus results
(500 MB OpenSubtitles, linux-kernel): [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

## Repo layout

```
wubugrep.c          CLI (argv0 multi-tool dispatch, parallel scan, emit)
wubre*.c/h          engine: compile/match/simd/dfa/bre/litpref modules
external_tests/     canonical GNU grep suites + differential runner
scripts/            gauntlet, adversarial fuzz, benchmark harnesses, PGO build
docs/               SOTA analysis, benchmarks, honesty ledger
```

## Integration note (WuBuOS)

Canonical checkout; WuBuOS symlinks it (`wubuos/src/tools/wubugrep ->
/home/wubu/wubugrep`) — one source of truth, no copies.

## License

WaefreBeorn Umbrella License v3.0 (SPDX: WaefreBeorn-UMV3).

## Standard

- **Layer:** text search tool (own SIMD matcher)
- **Build:** `make`
- **Verify:** `make test`
- **Docs:** `docs/` in this repo
- **Provenance:** own C11; no vendored third-party source without a note

Part of the ~WuBu~ tree: this repository is held to the same conventions as
the parent. See the parent's `docs/compendium/04-roadmap/submodule-standard.md`
for the checklist and why each item exists.
