#!/bin/bash
# full parity gauntlet: literal/BRE/ERE x plain/-n/-c vs GNU grep
cd "$(dirname "$0")/.."   # repo root — works from any checkout location
WUB="${WUB:-$PWD/wubugrep}"
C=${WUBUGREP_CORPUS:-/tmp/c3.txt}
fail=0
for pat in the error fox dog; do
  for opts in "" "-n" "-c" "-i" "-ni" "-F" "-nF"; do
    a=$("$WUB" $opts "$pat" $C | md5sum); b=$(grep $opts "$pat" $C | md5sum)
    [ "$a" = "$b" ] || { echo "LIT FAIL [$opts $pat]"; fail=1; }
  done
done
echo "literal sweep done (fail=$fail)"
for pat in 'the' 'error' 'a.c' '^the' 'dog$' 'the.*dog' 'a{2,4}b' 'foo\|bar' 'a\|b\|c' 'the.*e'; do
  a=$("$WUB" -G "$pat" $C | md5sum); b=$(grep -G "$pat" $C | md5sum)
  [ "$a" = "$b" ] || { echo "BRE FAIL [$pat]"; fail=1; }
  a=$("$WUB" -nG "$pat" $C | md5sum); b=$(grep -nG "$pat" $C | md5sum)
  [ "$a" = "$b" ] || { echo "BRE -n FAIL [$pat]"; fail=1; }
done
echo "BRE sweep done (fail=$fail)"
for pat in 'the' 'error' '[a-z]+' 'a+' '[0-9a-f]+' '[A-Z]' 'a.*b' 'foo|bar' 'a{2,4}' '(ab)+' '[0-9]' 'colou?r'; do
  a=$("$WUB" -E "$pat" $C | md5sum); b=$(grep -E "$pat" $C | md5sum)
  [ "$a" = "$b" ] || { echo "ERE FAIL [$pat]"; fail=1; }
  a=$("$WUB" -nE "$pat" $C | md5sum); b=$(grep -nE "$pat" $C | md5sum)
  [ "$a" = "$b" ] || { echo "ERE -n FAIL [$pat]"; fail=1; }
done
for pat in '\\bcat\\b' '\\bSherlock\\b' '\\w+\\s+Holmes'; do
  a=$("$WUB" -nE "$pat" $C | md5sum); b=$(grep -nE "$pat" $C | md5sum)
  [ "$a" = "$b" ] || { echo "WB FAIL: $pat"; fail=1; }
done
echo "ERE sweep done (fail=$fail)"
for pat in the error THE Error; do
  a=$("$WUB" -nE -i "$pat" $C | md5sum); b=$(grep -niE "$pat" $C | md5sum)
  [ "$a" = "$b" ] || { echo "ICASE-n ERE FAIL [$pat]"; fail=1; }
done
[ $fail = 0 ] && echo "=== FULL PARITY GAUNTLET: ALL BYTE-EXACT ==="
exit $fail
