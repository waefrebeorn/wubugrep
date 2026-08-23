
#include <stdio.h>
#include <string.h>
#include "wubre_internal.h"
/* search_buf=0 AND gate=0! The GATE rejects "cat cat\nxcat..." with required
   literal 'cat' PRESENT?! The gate must have a bug for \b patterns: litpref
   parses '\b' — the backslash-b... run[] gets 'b'? or the '\' handling?
   litpref parse_seq: c=='\\' && p+1<end => run[runn++]=p[1]='b', p+=2.
   So it extracts literal "b" + then 'c','a','t' -> run="bcat"! Required
   literal "bcat" is NOT in the buffer (no 'b' before cat... wait "xcat" no b)
   => gate rejects. THE LITPREF PARSER MUST UNDERSTAND ESCAPES: "\b" is a
   word-boundary anchor, contributes NO literal. */
int main(void){ printf("diagnosed\n"); return 0; }
