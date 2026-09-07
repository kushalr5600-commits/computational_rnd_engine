# counter8 — sky130A PnR smoke test (official flow.tcl sequence for this
# OpenROAD build, pointed at the installed CI PDK /usr/local/share/pdk/sky130A)
set test /tmp/The-OpenROAD-Project-OpenROAD-4feaf99/test
set pdk /usr/local/share/pdk/sky130A

read_lef $pdk/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
read_lef $pdk/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
read_liberty $pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
read_verilog /tmp/sky130_test/counter8.gate.v
link_design counter8
read_sdc /tmp/sky130_test/counter8.sdc

initialize_floorplan -site unithd -die_area {0 0 99.96 100.128} -core_area {9.996 10.08 89.964 90.048}
source $test/sky130hd/sky130hd.tracks
remove_buffers
place_pins -random -hor_layers met3 -ver_layers met2
tapcell -distance 14 -tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1
pdngen -verbose $test/sky130hd/sky130hd.pdn

set_global_routing_layer_adjustment met1 0.5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
set_global_routing_layer_adjustment met4 0.5
set_global_routing_layer_adjustment met5 0.5
set_routing_layers -signal met1-met5 -clock met3-met5
set_macro_extension 2
global_placement -routability_driven -density 0.3 -pad_left 4 -pad_right 4
place_pins -hor_layers met3 -ver_layers met2
write_def /tmp/sky130_test/counter8_gp.def

source $test/sky130hd/sky130hd.rc
set_wire_rc -signal -layer met2
set_wire_rc -clock -layer met5
set_dont_use {sky130_fd_sc_hd__probe_p_* sky130_fd_sc_hd__probec_p_*}
estimate_parasitics -placement
repair_design
repair_tie_fanout -separation 5 sky130_fd_sc_hd__conb_1/LO
repair_tie_fanout -separation 5 sky130_fd_sc_hd__conb_1/HI
set_placement_padding -global -left 2 -right 2
detailed_placement
report_worst_slack -min -digits 3
report_worst_slack -max -digits 3
report_tns -digits 3

repair_clock_inverters
clock_tree_synthesis -root_buf sky130_fd_sc_hd__clkbuf_1 -buf_list sky130_fd_sc_hd__clkbuf_1 -sink_clustering_enable
repair_clock_nets
estimate_parasitics -placement
set_propagated_clock [all_clocks]
repair_timing
detailed_placement
filler_placement sky130_fd_sc_hd__fill_*
check_placement -verbose

global_route -guide_file /tmp/sky130_test/counter8.route_guide -congestion_iterations 100
check_antennas -report_violating_nets -report_file /tmp/sky130_test/counter8.ant.log
write_verilog -remove_cells sky130_fd_sc_hd__fill_* /tmp/sky130_test/counter8.routed.v

set_thread_count 2
detailed_route -guide /tmp/sky130_test/counter8.route_guide \
  -output_guide /tmp/sky130_test/counter8_output_guide.mod \
  -output_drc /tmp/sky130_test/counter8_route_drc.rpt \
  -output_maze /tmp/sky130_test/counter8_maze.log \
  -verbose 0
detailed_route_num_drvs

define_process_corner -ext_model_index 0 X
extract_parasitics -ext_model_file $test/sky130hd/sky130hd.rcx_rules
write_spef /tmp/sky130_test/counter8.spef
read_spef /tmp/sky130_test/counter8.spef

report_checks -path_delay min_max -format full_clock_expanded -fields {input_pin slew capacitance} -digits 3
report_worst_slack -min -digits 3
report_worst_slack -max -digits 3
report_tns -digits 3
report_check_types -max_slew -max_capacitance -max_fanout -violators -digits 3
report_clock_skew -digits 3
report_power
report_floating_nets -verbose
report_design_area
write_def /tmp/sky130_test/counter8_route.def
puts "SMOKE_FLOW_DONE"
