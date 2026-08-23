# WuBuGrep — 100 Improvements (To Be Continued)

> The roadmap. Every item here is a real, admitted gap or an opportunity,
> informed by studying what ripgrep, ugrep, GNU grep, and the Hyperscan
> literature actually do — plus our own measured weaknesses. None are hidden.
> Order within categories is roughly priority; categories are not.
>
> Status legend: `[ ]` open · `[-]` in progress · `[x]` done.

---

## A. Fixed-overhead & startup cost (the ~13–20 ms floor)

1. `[ ]` Profile and itemize the per-file setup path (mmap setup, chunk split, thread spawn, gate) into named costs.
2. `[ ]` Skip the chunk-split entirely for files under ~1 MB (single-thread scan).
3. `[ ]` Lazy thread pool: reuse one pool process-wide instead of spawning per file.
4. `[ ]` Thread-affinity pinning to reduce migration jitter on reject rows (spread up to ~30%).
5. `[ ]` Avoid zeroing/initializing structures that reject patterns never touch.
6. `[ ]` Single allocation arena for the per-file scan context; free once.
7. `[ ]` Fuse `buffer_is_binary` + newline pre-scan + literal gate into ONE pass for all shapes (currently fused only for single-alt).
8. `[ ]` Cheaper argv parse / config resolution (measurable at 4 ms competitor floor).
9. `[ ]` Precompute the line-index only when `-n` is active AND first match fires (done for rejects; verify dense-match cost).
10. `[ ]` Measure startup vs scan split with `perf stat` and publish the breakdown.

## B. Matcher throughput (the scan itself)

11. `[ ]` Vectorized DFA walk (`wubre_dfa_walk_avx2`): 16 bytes/iter via parallel table lookup to break the scalar data-dependency chain (~1 byte/5 cycles).
12. `[ ]` Generalize the SIMD class-skip from hardcoded ranges to ANY character class (arbitrary `skip_lo/skip_hi` tables) — kills the residual `[0-9]`-style floor.
13. `[ ]` Harry-class matcher (the successor to Teddy in the Hyperscan literature): register-only multi-literal matching beyond Teddy's bucket scheme.
14. `[ ]` AVX-512 port of Teddy/gate/fused scans where available (VL=64 halves iteration count); keep AVX2/scalar fallbacks.
15. `[ ]` Verify-step hashing for multi-literal alternations: replace naive candidate verification with bucket-hash confirmation (rg's approach; our tracked ~2× gap).
16. `[ ]` Auto-possessification at compile time: `a*!b` style possessive quantifiers to cut NFA backtracking states.
17. `[ ]` DFA state-capping improvements: smarter blow-up detection than flat `DFA_CAP_MAX`, e.g. lazy per-layer caps.
18. `[ ]` Shifty-Teddy variant: PEXT-based fingerprint extraction on BMI2 hardware.
19. `[ ]` Reverse-scan for anchored-at-end literals (`dog$`): memrchr from buffer end.
20. `[ ]` Composite prefilter: choose among single-literal probe / Teddy sweep / DFA by measured pattern shape, not fixed dispatch order.

## C. Literal extraction & prefilter intelligence

21. `[ ]` Corpus-measured literal rarity: cheap first-pass byte histogram (SIMD popcount pass) replacing the static English prior when a file is re-scanned.
22. `[ ]` Extend rarest-probe soundness argument to two-literal probes for multi-alt prefilters (probe pairs whose joint absence is provable).
23. `[ ]` Suffix-literal extraction (match ugrep's RSA tail bytes, not just first-byte rarity).
24. `[ ]` Case-fold-aware SIMD gate for ICASE (currently falls back to exact scalar fold path).
25. `[ ]` Required-prefix vs required-anywhere distinction: anchored prefixes allow skipping whole regions, not just rejecting lines.
26. `[ ]` Minimal-DNF reduction of the literal-set (merge overlapping alternatives before gating).
27. `[ ]` Detect "impossible" patterns at compile time (contradictory requirements like `\bword\b.{0}`) and fail fast.
28. `[ ]` Per-alternative density estimation to route each alternation branch to its best engine.
29. `[ ]` UTF-8-aware literal gates once Unicode support lands (see §G).

## D. Directory traversal & I/O

30. `[ ]` io_uring batched stat/open/read pipeline for `-r` traversal (the tracked ~10× gap vs rg on WSL2).
31. `[ ]` statx batching: one syscall amortizing many metadata queries.
32. `[ ]` gitignore-aware skipping (`.gitignore`, `.ignore`, global/exclude files) like ripgrep.
33. `[ ]` Hidden-file and VCS-dir default skips with grep-compatible opt-outs (`--no-ignore`-style flags documented as extensions).
34. `[ ]` Parallel enumeration + work-stealing instead of batch-flush ordering (keep ordered output via sequence numbers).
35. `[ ]` Directory-entry sorting lazily: sort only when output order requires it.
36. `[ ]` mmap vs read decision per file size/filesystem (mmap loses on network FS; measure and adapt).
37. `[ ]` `MAP_POPULATE` option for large single-file scans (page-fault amortization).
38. `[ ]` Hugepage-backed mmap hint for corpora > 1 GB.
39. `[ ]` Skip-traversal of symlink loops with cycle detection (correctness hardening for pathological trees).
40. `[ ]` Benchmark suite for traversal: kernel-tree, many-small-files, deep-nesting, cold-cache runs — published honestly.

## E. Output & emit path

41. `[ ]` Batched writev-style emit for dense `-n` matches (currently per-line writes dominate dense-match wall time).
42. `[ ]` Bulk line-index build vectorized (SIMD newline scan already exists — wire it to index construction).
43. `[ ]` Lock-free per-chunk result buffers with ordered drain (remove mutex contention on hot chunks).
44. `[ ]` Color output with match highlighting (`--color=auto/always/never`) — currently only suppressed via `--no-color`.
45. `[ ]` Context lines `-A/-B/-C` with group separators (`--`, byte offsets) — full GNU compatibility set.
46. `[ ]` `--only-matching` / `-o` (print matched parts, one per line).
47. `[ ]` `--replace`/substitution output mode.
48. `[ ]` `--files-without-match` (grep has it; we don't).
49. `[ ]` `--include-from`/`--exclude-from` file lists.
50. `[ ]` JSON output mode (`--json`) for tool integration (rg parity).

## F. Regex features & GNU parity edges

51. `[ ]` POSIX equivalence classes `[[=e=]]` and collating symbols `[[.ch.]]`: parser accepts them; verify semantics against glibc locales exhaustively.
52. `[ ]` Locale-aware case folding behind an explicit flag (default stays ASCII for determinism).
53. `[ ]` `{n,m}` with >255 expansion guard: streaming interval expansion instead of materializing copies (memory bound).
54. `[ ]` BRE `\{n,m\\}` corner cases: full empirical parity sweep against glibc regex, including malformed intervals.
55. `[ ]` Word-boundary Unicode definition (`is_word` over multibyte sequences) once UTF-8 lands.
56. `[ ]` Named backreferences `\k<name>` (extension beyond our `\1..9`; document as such).
57. `[ ]` Atomic groups `(?>...)` as a DoS-hardening extension (document divergence deliberately).
58. `[ ]` Lookahead `(?=...)` via a second-pass engine — scoped, honest extension (rg lacks these too; PCRE2 territory).
59. `[ ]` Fuzz the BRE translator against glibc `regcomp/regexec` directly (not just grep CLI), thousands of random patterns.
60. `[ ]` Differential fuzz vs PCRE2 with `-P`-style flag if ever added — know exactly which constructs diverge.

## G. Unicode & encodings

61. `[ ]` UTF-8 input validation (cheap SIMD validation pass) and correct byte-vs-char semantics switch.
62. `[ ]` Character classes over Unicode code points (`[à-ÿ]`, `\p{L}` minimal property set).
63. `[ ]` UTF-16/UTF-32 input detection via BOM + heuristic (ugrep does this).
64. `[ ]` Line-ending handling: CRLF and CR-only files (grep's `--null-data` cousin; currently LF-only assumptions in several paths).
65. `[ ]` Case folding: full simple case folding (Common+Greek+Cyrillic at minimum), table-driven, DFA-compatible.
66. `[ ]` Document precisely what remains ASCII-only after all of the above (honesty ledger entry).

## H. Compressed / archive / special inputs

67. `[ ]` Search gzip-compressed files (`-z`): own inflate (we make our own — WuBuOS already has kernel-owned ZIP/CAB decoders to share).
68. `[ ]` zstd/xz/bz2 decompression filters (own decoders per repo policy, no third-party libs).
69. `[ ]` tar/zip member traversal for archive search.
70. `[ ]` Binary-file hexdump match output (`--binary-files=hexdump` style).
71. `[ ]` stdin streaming mode with bounded-memory chunking (currently file-oriented mmap design).
72. `[ ]` Process substitution / FIFO input support (non-seekable inputs).

## I. Usability & CLI surface

73. `[ ]` Config file support (`~/.wubugreprc`, WUBUGREP_OPTIONS env like GREP_OPTIONS done right).
74. `[ ]` File-type presets (`-t c`, `-t rust`, `-t markdown`) via extension+shebang+magic tables.
75. `[ ]` Interactive query TUI (ugrep's killer feature) — even a minimal filter-as-you-type mode.
76. `[ ]` Boolean query mode: AND/OR/NOT across patterns (`--and/--or/--not`) without regex alternation gymnastics.
77. `[ ]` Fuzzy/approximate search mode (edit-distance ≤ k) — Hyperscan-style approximate matching, our own bit-parallel implementation.
78. `[ ]` `--stats` output (bytes scanned, files visited, threads used, engine dispatched per pattern).
79. `[ ]` Man page + shell completions (bash/zsh/fish).
80. `[ ]` `wubucat`/argv0 sibling tools documented and tested as first-class citizens.

## J. Correctness infrastructure

81. `[ ]` Run the FULL canonical GNU grep suite nightly in CI (ere.tests + bre.tests + ffrtfree extended suites if obtainable), not just locally.
82. `[ ]` Cross-platform CI matrix: gcc/clang × -O0/-O2/-O3 × AVX2/no-AVX2 (portable build) — catch target-attribute drift.
83. `[ ]` ASan/UBSan run integrated into `make test` (currently manual command).
84. `[ ]` Fuzz harness with coverage feedback (AFL++/libFuzzer-style, our own corpus format) running minutes-not-hours per session.
85. `[ ]` Property-based oracle: independent naive matcher (Python/Rust reference) diffed on random corpora × random patterns, continuous.
86. `[ ]` Valgrind helgrind/DRD pass over the parallel scanner (TSAN equivalent) — thread races beyond the Teddy collector bug class.
87. `[ ]` Determinism test: same input × same flags → byte-identical output under varying thread counts.
88. `[ ]` Corpus regression vault: every bug found becomes a pinned test corpus + pattern pair (institutional memory against silent regressions).
89. `[ ]` Benchmark integrity CI job: detect invalid competitor invocations (`rg -E`-class traps) automatically before any number is published.

## K. Measurement honesty & scale

90. `[ ]` Multi-GB benchmark surface: linux-kernel tree, 500MB subtitles, and a cold-cache protocol — one published table, both cache states.
91. `[ ]` p50/p95/p99 latency distribution reporting, not just min/max (single-run anecdotes retired permanently).
92. `[ ]` Power/energy measurement on sustained scans (every-cycle-counts extends to joules).
93. `[ ]` Non-x86 bring-up: NEON port of the SIMD layer (ARM64), scalar fallback verified on RISC-V.
94. `[ ]` Windows-leg proof: build + differential-test under WuBuOS hosted/wine legs per RUN POLICY (no host-tool cheating).
95. `[ ]` Reproducible-benchmark script pinned to commit hashes of competitors (rg/ugrep versions baked into results JSON).

## L. Architecture & code quality

96. `[ ]` Split wubugrep.c (CLI+walker+emit monolith) into walker.c/emit.c/options.c — opaque-module discipline like the engine.
97. `[ ]` Kill remaining implicit POSIX assumptions audit (`strdup`-class traps): -std=c11 strict build with feature macros explicit.
98. `[ ]` Engine API stability doc: which wubre_* functions are public contract vs internal.
99. `[ ]` Fuzz-driven compile-time budget: guarantee `wubre_compile` terminates on arbitrary hostile input (formal step budget).
100. `[ ]` The compiler-project crossover: WuBuGrep becomes the self-hosted search primitive of WuBuOS — dogfooded inside the AGI kernel, benchmarked through its own 9P/exec stack, proving the toolchain feeds itself.

---

*This list is alive. Items get added when research exposes a new gap; items get
checked off only with a committed test + measurement. No claim moves to the
README until it survives the gauntlet.*
