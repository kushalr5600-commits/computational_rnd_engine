ly = RBA::Layout.new
ly.dbu = 0.001
top = ly.create_cell("TOP")
l1 = ly.layer(1, 0)
top.shapes(l1).insert(RBA::Box.new(0, 0, 10000, 5000))
ly.write("/tmp/kl_test.gds")
sz = File.size("/tmp/kl_test.gds")
puts "WROTE_GDS #{sz} bytes"
ly2 = RBA::Layout.new
ly2.read("/tmp/kl_test.gds")
puts "READBACK cells=#{ly2.cells} hasTOP=#{ly2.has_cell?("TOP")}"
puts "RBA_ROUNDTRIP_OK"
