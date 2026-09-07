#!/bin/sh
echo '=== magicdnull/magicexec present?:'
ls -la /usr/local/lib/magic/tcl/ | grep -E 'magicdnull|magicexec'
echo '=== full magic run output:'
echo quit | timeout 30 /usr/local/bin/magic -dnull -noconsole 2>&1 | head -12
echo '=== exit code check:'
echo quit | timeout 30 /usr/local/bin/magic -dnull -noconsole >/dev/null 2>&1 ; echo RC=$?
echo MAGIC_DBG_DONE
