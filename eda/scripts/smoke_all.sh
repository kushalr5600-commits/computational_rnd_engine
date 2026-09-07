#!/usr/bin/env bash
# Replicate eda-doctor smoke tests, each bounded by its own timeout.
cd /tmp/smoke
run() {
  local name="$1"; shift
  local to="${1:-15}"; shift
  local t0=$(date +%s)
  out=$(timeout "$to" "$@" 2>&1); rc=$?
  local dt=$(( $(date +%s) - t0 ))
  case $rc in
    0)   st=PASSED ;;
    124) st=TIMEOUT ;;
    *)   st="FAILED" ;;
  esac
  echo "[$name] $st (${dt}s)"
  [ "$st" = "PASSED" ] && echo "  out: $(echo "$out" | tail -1)"
  [ "$st" != "PASSED" ] && echo "  err: rc=$rc :: $(echo "$out" | tail -2)"
}
echo "== tool smoke tests =="
run verilator 15 verilator --lint-only --top-module smoke smoke.sv
run iverilog 15 iverilog -g2012 -o smoke.vvp smoke.sv smoke_tb.sv
run vvp      15 vvp -n smoke.vvp
run yosys    20 yosys -q -p "read_verilog -sv smoke.sv; synth -top smoke; stat"
run abc      10 abc -c print_stats
run sby      20 sby -f smoke.sby
run openroad 10 openroad -version
run opensta  10 opensta -version -no_init
run magic    10 magic -dnull -noconsole -version
run netgen   15 netgen -batch -noconsole smoke.tcl
run klayout  10 klayout -v
run ghdl     10 ghdl --version
echo "== done =="
