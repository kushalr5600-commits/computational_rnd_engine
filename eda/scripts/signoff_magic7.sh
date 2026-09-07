#!/bin/sh
apt-get install -y -qq libglu1-mesa >/tmp/apt_glu.log 2>&1 && echo GLU_APT_OK || { echo GLU_FAIL; tail -3 /tmp/apt_glu.log; }
echo '=== ALL missing libs for tclmagic.so + magicexec:'
ldd /usr/local/lib/magic/tcl/tclmagic.so 2>/dev/null | grep 'not found'
ldd /usr/local/lib/magic/tcl/magicexec 2>/dev/null | grep 'not found'
echo LDD_SCAN_DONE
echo '=== magic run:'
timeout 30 /usr/local/bin/magic -dnull -noconsole < /tmp/mver.tcl 2>&1 | head -10
echo MAGIC_GLU_DONE
