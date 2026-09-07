#!/bin/sh
sed -n '55,185p' /tmp/signoff/klayout_build2.log | cut -c1-110
echo SLICE_DONE
