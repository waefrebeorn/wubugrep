# WuBuGrep — strict C11, zero dependencies
CC      ?= cc
CFLAGS  ?= -O3 -flto -march=native -std=c11 -Wall -Wextra
ENGINE   = wubre.c wubre_compile.c wubre_match.c wubre_simd.c wubre_bre.c wubre_dfa.c wubre_litpref.c

all: wubugrep wubre_test

wubugrep: wubugrep.c $(ENGINE) wubre.h wubre_internal.h
	$(CC) $(CFLAGS) -I. -o $@ wubugrep.c $(ENGINE)

# portable build: no -march=native, scalar fallbacks engage automatically
portable:
	$(CC) -O2 -std=c11 -Wall -I. -o wubugrep wubugrep.c $(ENGINE)

static: wubugrep.c $(ENGINE)
	$(CC) $(CFLAGS) -static -I. -o wubugrep_static wubugrep.c $(ENGINE)

wubre_test: wubre_test.c wubre.c $(ENGINE)
	$(CC) -O2 -std=c11 -I. -o $@ wubre_test.c wubre.c $(ENGINE)
	./wubre_test

test: wubre_test
	cd external_tests && python3 run_grep_tests.py --mode ere ere.tests
	cd external_tests && python3 run_grep_tests.py --mode bre bre.tests

gauntlet: wubugrep
	bash scripts/gauntlet.sh

fuzz: wubugrep
	bash scripts/fuzz_adversarial.sh

bench: wubugrep
	bash scripts/bench_fresh.sh

clean:
	rm -f wubugrep wubugrep_static wubre_test *.gcda *.gcno

.PHONY: all portable static test gauntlet fuzz bench clean
