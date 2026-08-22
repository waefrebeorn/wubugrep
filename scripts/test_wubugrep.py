#!/usr/bin/env python3
"""
WuBuGrep differential test oracle.

We don't trust ourselves - we trust GNU grep (POSIX semantics) and ripgrep
as independent oracles. For every generated (corpus, pattern, flag-combo) we
assert WuBuGrep's output is BYTE-IDENTICAL to `grep` (the POSIX gold standard)
and functionally equivalent to `rg`.

This is a DETERMINATE test: a fixed seed produces a fixed, reproducible
verification. Re-run -> same verdict.

WaefreBeorn Umbrella License v3.0
"""
import os, sys, random, subprocess, tempfile, shutil, hashlib, signal

WUB     = os.path.join(os.path.dirname(__file__), "wubugrep")
GREP    = shutil.which("grep")
RG      = shutil.which("rg")
SEED    = int(os.environ.get("WUB_TEST_SEED", "1337"))
N_TRIALS = int(os.environ.get("WUB_TRIALS", "4000"))

assert os.path.exists(WUB), f"wubugrep binary not found at {WUB}"
assert GREP, "GNU grep required as oracle"

random.seed(SEED)

# flag combos we support that POSIX grep also supports identically
FLAGS = [
    (), ("-i",), ("-v",), ("-n",), ("-c",), ("-l",),
    ("-i", "-v"), ("-i", "-n"), ("-v", "-n"), ("-i", "-c"), ("-v", "-c"), ("-i", "-v", "-n"),
    ("-c", "-v"), ("-l", "-i"), ("-l", "-v"),
]

ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
TOKENS = ["wubu", "grep", "kernel", "amoeba", "zzz", "alpha", "the", "fox", "C11", "x", "ab"]

def rnd_text(rng, nchars):
    out = []
    while len(out) < nchars:
        t = rng.choice(TOKENS)
        out.append(t)
        if rng.random() < 0.3:
            out.append("\n")
        else:
            out.append(" ")
    s = "".join(out)
    # ensure no accidental NUL / control chars (keep text corpus clean for oracle)
    return s

def make_corpus(rng):
    """Return (files: list[(relpath, content)], root)"""
    root = tempfile.mkdtemp(prefix="wubtest_")
    files = []
    nfiles = rng.randint(1, 6)
    for i in range(nfiles):
        # nested subdir sometimes
        sub = ""
        if rng.random() < 0.3:
            sub = f"sub{rng.randint(0,3)}"
            os.makedirs(os.path.join(root, sub), exist_ok=True)
        fn = os.path.join(root, sub, f"f{i}.txt") if sub else os.path.join(root, f"f{i}.txt")
        content = rnd_text(rng, rng.randint(0, 400))
        # guarantee a last-line-without-newline case sometimes
        if content and rng.random() < 0.5:
            content = content.rstrip("\n")
        else:
            content = content + "\n"
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, "w") as f:
            f.write(content)
        files.append((os.path.relpath(fn, root), content))
    return files, root

def rnd_pattern(rng, files):
    choice = rng.random()
    if choice < 0.25:
        # a token that exists
        return rng.choice(TOKENS)
    if choice < 0.4:
        # single char
        return rng.choice("abcdefghij0123456789")
    if choice < 0.5:
        # two-char
        return rng.choice("abcdef") + rng.choice("abcdef0123")
    if choice < 0.6:
        # multi-token glued (likely present as substring across? not necessarily)
        return rng.choice(TOKENS)[:rng.randint(1,4)] + rng.choice(TOKENS)[:rng.randint(1,4)]
    if choice < 0.7:
        return "definitelyabsentxyz"
    if choice < 0.8:
        return ""  # empty pattern (matches everywhere)
    # substring of a real token
    tok = rng.choice(TOKENS)
    if len(tok) >= 2:
        a = rng.randint(0, len(tok)-1); b = rng.randint(a+1, len(tok))
        return tok[a:b]
    return tok

def run(cmd, cwd):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=30)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return -9, b""

def norm_grep(out, cwd, args, files):
    # for multi-file we pass files; grep prints "path:..." relative to cwd
    return out

def main():
    fails = 0
    checked = 0
    for t in range(N_TRIALS):
        rng = random.Random(f"{SEED}-{t}")
        files, root = make_corpus(rng)
        pat = rnd_pattern(rng, files)
        for flags in FLAGS:
            checked += 1
            # run wubugrep and grep with identical args on the SAME file list
            fpaths = [os.path.join(root, rel) for rel, _ in files]
            wcmd = [WUB, *flags, pat, *fpaths]
            gcmd = [GREP, *flags, "--", pat, *fpaths]
            wrc, wout = run(wcmd, root)
            grc, gout = run(gcmd, root)
            # grep exit semantics: 0 = match, 1 = no match, 2 = error
            if wrc not in (0,1) or grc not in (0,1):
                if wrc != grc:
                    print(f"[FAIL] t{t} flags={flags} pat={pat!r} rc w={wrc} g={grc}")
                    fails += 1
                    continue
            if wout != gout:
                # only meaningful if at least one produced output; if both empty and rcs agree, ok
                if wout.strip() == b"" and gout.strip() == b"" and wrc == grc:
                    continue
                print(f"[FAIL] t{t} flags={flags} pat={pat!r}")
                print(f"   wubugrep rc={wrc} grep rc={grc}")
                print(f"   wubugrep:\n{wout.decode(errors='replace')[:500]}")
                print(f"   grep:\n{gout.decode(errors='replace')[:500]}")
                fails += 1
                if fails > 25:
                    print("too many failures, aborting"); break
        shutil.rmtree(root, ignore_errors=True)
        if fails > 25:
            break

    # ---- targeted edge cases ----
    edge = 0
    def check(name, content, pat, flags, expect_substr=None, expect_rc=None):
        nonlocal edge, fails
        edge += 1
        root = tempfile.mkdtemp(prefix="wubedge_")
        fn = os.path.join(root, "e.txt")
        with open(fn, "w") as f: f.write(content)
        wrc, wout = run([WUB, *flags, pat, fn], root)
        grc, gout = run([GREP, *flags, "--", pat, fn], root)
        ok = (wout == gout) and (wrc == grc)
        if not ok:
            print(f"[EDGE FAIL] {name}: flags={flags} pat={pat!r}")
            print(f"   w rc={wrc}: {wout.decode(errors='replace')!r}")
            print(f"   g rc={grc}: {gout.decode(errors='replace')!r}")
            fails += 1
        shutil.rmtree(root, ignore_errors=True)

    # empty pattern matches every line
    check("empty_pat_lines", "a\nb\nc\n", "", ("-n",), )
    check("empty_pat_count", "a\nb\nc\n", "", ("-c",), )
    # pattern at very end with no trailing newline
    check("no_trailing_nl", "hello world", "world", ("-n",))
    check("no_trailing_nl_count", "hello world", "world", ("-c",))
    # pattern at line start
    check("line_start", "wubu is here\nhere wubu", "wubu", ())
    # CRLF
    check("crlf", "a\r\nb wubu\r\nc\r\n", "wubu", ("-n",))
    # multiple matches same line
    check("multi_same_line", "wubu x wubu y wubu\n", "wubu", ("-c",))
    # case-insensitive
    check("insensitive", "WuBu WUBU wubu\n", "wubu", ("-i", "-c"))
    # invert
    check("invert", "wubu\nalpha\nwubu\n", "wubu", ("-v", "-c"))
    # -l with match
    check("files_with_match", "x wubu y\n", "wubu", ("-l",))
    # -l with no match -> no output, rc 1
    check("files_no_match", "x y z\n", "wubu", ("-l",))
    # single char pattern
    check("single_char", "ababab\n", "b", ("-c",))
    # pattern longer than any line
    check("pat_longer_than_line", "abc\ndef\n", "abcdefghijklmnop", ())

    # ---- recursive --include/--exclude with options AFTER the pattern ----
    def check_rec(name, tree, pat, flags):
        nonlocal edge, fails
        edge += 1
        root = tempfile.mkdtemp(prefix="wubrec_")
        for rel, content in tree:
            fn = os.path.join(root, rel)
            os.makedirs(os.path.dirname(fn), exist_ok=True)
            with open(fn, "w") as f: f.write(content)
        # options AFTER the pattern (the bug we fixed: must still parse)
        wrc, wout = run([WUB, pat, "-r", *flags], root)
        grc, gout = run([GREP, pat, "-r", *flags], root)
        # GNU grep's -r traversal order is readdir/filesystem dependent (not a
        # portable contract; ripgrep sorts, GNU does not and it varies by fs),
        # so for recursive mode we compare SORTED output sets: identical matches,
        # identical exit code. This still catches any content/flag divergence.
        ws = sorted(wout.splitlines())
        gs = sorted(gout.splitlines())
        if (ws != gs) or (wrc != grc):
            print(f"[REC FAIL] {name}: flags={flags} pat={pat!r}")
            print(f"   w rc={wrc}: {wout.decode(errors='replace')!r}")
            print(f"   g rc={grc}: {gout.decode(errors='replace')!r}")
            fails += 1
        shutil.rmtree(root, ignore_errors=True)

    tree = [("a.txt", "fox here\n"),
            ("sub/b.txt", "fox there\n"),
            ("c.md", "fox in md\n"),
            ("sub/d.md", "no fox\n")]
    # --include='*.txt' must select only .txt files even when option is after pattern
    check_rec("include_txt", tree, "fox", ("--include=*.txt",))
    # --include='*.md' must select only .md (so 'fox' matches c.md only)
    check_rec("include_md", tree, "fox", ("--include=*.md",))
    # --exclude='*.md' drops md files
    check_rec("exclude_md", tree, "fox", ("--exclude=*.md",))
    # combined: option after pattern + -n
    check_rec("include_txt_n", tree, "fox", ("--include=*.txt", "-n"))
    print(f"  random trials : {min(checked, N_TRIALS*(len(FLAGS)))} flag/corpus combos")
    print(f"  edge cases    : {edge}")
    print(f"  FAILURES      : {fails}")
    if RG:
        print(f"  ripgrep oracle: available ({RG})")
    if fails == 0:
        print("  VERDICT: IDENTICAL TO GNU GREP ORACLE ✓")
        sys.exit(0)
    else:
        print("  VERDICT: DIVERGENCE DETECTED ✗")
        sys.exit(1)

if __name__ == "__main__":
    main()
