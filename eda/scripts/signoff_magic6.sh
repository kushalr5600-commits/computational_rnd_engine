#!/bin/sh
echo '=== apt install libgl1:'
apt-get update -qq >/tmp/apt_up.log 2>&1 && apt-get install -y -qq libgl1 >/tmp/apt_gl.log 2>&1 && echo APT_OK || { echo APT_FAIL; tail -5 /tmp/apt_gl.log; }
echo '=== magic run:'
timeout 30 /usr/local/bin/magic -dnull -noconsole < /tmp/mver.tcl 2>&1 | head -10
echo MAGIC_GL_DONE
