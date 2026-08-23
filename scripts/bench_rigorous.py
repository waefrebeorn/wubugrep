#!/usr/bin/env python3
"""
WuBuGrep rigorous benchmark suite — modeled on ripgrep's benchsuite.

Methodology (mirroring BurntSushi's benchsuite):
  * Named benchmarks, each with a fixed pattern + corpus + per-tool command
    line chosen to be as FAIR as possible (same flags semantics: -n lines,
    count vs lines matched across tools).
  * warmup_iter warmup runs (page cache), then bench_iter timed runs.
  * Reports mean +/- stdev, and — critically — VERIFIES that every tool
    returns the same match output for the same benchmark (line counts).
    A tool whose line count diverges from the others is flagged: a speed
    number from tools doing different work is meaningless.
  * Fresh subprocess per iteration (no in-process state reuse).
  * Timing via time.perf_counter around subprocess.run (wall clock of the
    child process; this is what hyperfine-style harnesses measure).

Corpora (see corpora/README):
  subtitles-en : single large natural-language file (OPUS OpenSubtitles)
  linux        : many-file source tree (shallow kernel clone)
  c3           : our original synthetic corpus (kept for continuity)

Usage:
  python3 scripts/bench_rigorous.py [--corpora DIR] [--iter N] [--warmup N]
      [--filter SUBSTR] [--tools rg,grep,ugrep,wubugrep] [--json OUT]
"""
import argparse
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

def find_tool(name):
    """locate competitor binaries; wubugrep is built at repo root"""
    if name == "wubugrep":
        p = os.path.join(REPO, "wubugrep")
        return p if os.path.exists(p) else None
    if name == "ugrep":
        from shutil import which
        return which("ugrep") or "/home/wubu/opt/ugrep_study/ugrep/bin/ugrep"
    from shutil import which
    return which(name)

def corpus_paths(corpora_dir):
    d = {}
    sub = os.path.join(corpora_dir, "subtitles-en.sample")
    if os.path.exists(sub): d["subtitles-en"] = ("single", sub)
    lin = os.path.join(corpora_dir, "linux-kernel")
    if os.path.isdir(lin) and os.listdir(lin): d["linux"] = ("dir", lin)
    c3 = "/tmp/c3.txt"
    if os.path.exists(c3): d["c3-synth"] = ("single", c3)
    return d

# ---- benchmark definitions -------------------------------------------------
# each: (name, pattern, mode) where mode selects CLI flags per tool.
# Patterns mirror ripgrep's benchsuite where applicable.
BENCHES = [
    # --- literals ---
    ("literal",              "Sherlock Holmes"),
    ("literal_casei",        "sherlock holmes"),           # run with -i
    ("literal_word",         r"\bSherlock\b"),             # word boundary
    ("alternates_literal",   "Sherlock Holmes|John Watson|Irene Adler|Inspector Lestrade|Professor Moriarty"),
    # --- classes / quantifiers (our old suite, kept for continuity) ---
    ("class_lower",          "[a-z]+"),
    ("class_upper_reject",   "[A-Z]"),
    ("digit_reject",         "[0-9]"),
    ("quantifier_reject",    "a{2,4}"),
    # --- literal-defeating (the honest stress test) ---
    ("no_literal",           r"\w{5}\s+\w{5}\s+\w{5}\s+\w{5}\s+\w{5}"),
    # --- surrounding words (rg's hardest real-world shape) ---
    ("surround_words",       r"\w+\s+Holmes\s+\w+"),
]

CASEI = {"literal_casei"}

def build_cmd(tool, pat, mode, target):
    """Returns the argv to run: [binary, flags..., PATTERN, CORPUS]."""
    binp = find_tool(tool)
    flags = ["-n"]           # line numbers everywhere (rg/grep/ugrep/wubu all support)
    if pat in CASEI: flags.append("-i")
    regex = ["-E"]           # ERE for grep; rg/ugrep take regex by default
    if tool == "wubugrep":
        return [binp] + flags + ["-E", pat, target]
    if tool == "grep":
        return [binp] + flags + ["-E", pat, target]
    if tool in ("rg", "ugrep"):
        return [binp] + flags + [pat, target]
    raise ValueError(tool)

def run_once(cmd, cwd=None):
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, timeout=120, cwd=cwd)
    dt = time.perf_counter() - t0
    return dt, p.stdout.decode("utf-8", "replace").count("\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpora", default=os.path.expanduser("~/corpora"))
    ap.add_argument("--iter", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--filter", default="")
    ap.add_argument("--tools", default="wubugrep,grep,rg,ugrep")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    tools = [t.strip() for t in args.tools.split(",") if find_tool(t.strip())]
    missing = [t.strip() for t in args.tools.split(",") if not find_tool(t.strip())]
    if missing: print(f"# skipping unavailable tools: {missing}")

    corpora = corpus_paths(args.corpora)
    if not corpora:
        print("No corpora found. See corpora setup in README.", file=sys.stderr)
        sys.exit(1)

    print(f"tools: {tools}")
    print(f"warmup={args.warmup} iter={args.iter}\n")

    results = []
    for cname, (kind, path) in sorted(corpora.items()):
        for (bname, pat) in BENCHES:
            full = f"{cname}/{bname}"
            if args.filter and args.filter not in full: continue
            print(f"--- {full} (pattern: {pat[:60]}{'...' if len(pat)>60 else ''})")
            rows = {}
            counts = set()
            for tool in tools:
                cmd = build_cmd(tool, pat, "lines", path)
                if kind == "dir":
                    # directory search: insert -r after the binary for tools
                    # that need it (rg/ugrep/grep recurse only with -r;
                    # rg actually searches cwd by default but -r is explicit
                    # and fair across all four).
                    if "-r" not in cmd:
                        cmd.insert(1, "-r")
                # warmup
                for _ in range(args.warmup):
                    try: run_once(cmd)
                    except subprocess.TimeoutExpired: break
                times = []
                ok = True
                for _ in range(args.iter):
                    try:
                        dt, nlines = run_once(cmd)
                        times.append(dt); counts.add((tool, nlines))
                    except subprocess.TimeoutExpired:
                        ok = False; break
                if not ok or not times:
                    print(f"  {tool:<12} TIMEOUT/SKIP"); continue
                mean = statistics.mean(times); stdev = statistics.stdev(times) if len(times)>1 else 0.0
                rows[tool] = (mean, stdev)
                print(f"  {tool:<12} {mean*1000:9.2f} ms ± {stdev*1000:6.2f}   (lines/it varies: {[c[1] for c in sorted(counts) if c[0]==tool][:1]})")
            # parity check: all tools must agree on match COUNT with each other
            per_tool_counts = {t: set(n for tt,n in counts if tt==t) for t in rows}
            distinct = {frozenset(v) for v in per_tool_counts.values() if v}
            if len(distinct) > 1:
                print(f"  !! LINE-COUNT DIVERGENCE: {per_tool_counts}")
            fastest = min(rows.items(), key=lambda kv: kv[1][0])
            print(f"  => fastest: {fastest[0]}\n")
            results.append({"bench": full, "pattern": pat,
                            "times_ms": {t: (rows[t][0]*1000, rows[t][1]*1000) for t in rows},
                            "counts": {t: sorted(per_tool_counts[t]) for t in rows}})

    if args.json:
        import json
        with open(args.json, "w") as f: json.dump(results, f, indent=1)
        print(f"# wrote {args.json}")

if __name__ == "__main__":
    main()
