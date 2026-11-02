import ezdxf

doc = ezdxf.new("R2018", setup=True)
doc.header["$INSUNITS"] = 6  # metres
doc.layers.add("PARCELS", color=3)
doc.layers.add("ROADS", color=1)
doc.layers.add("BUILDINGS", color=5)
doc.layers.add("TEXT", color=7)
msp = doc.modelspace()
x0, y0 = 500000, 3950000  # UTM-ish eastings/northings
for i in range(3):
    for j in range(2):
        x, y = x0 + i * 60, y0 + j * 40
        msp.add_lwpolyline([(x, y), (x + 50, y), (x + 50, y + 30), (x, y + 30)], close=True, dxfattribs={"layer": "PARCELS"})
        msp.add_lwpolyline([(x + 10, y + 5), (x + 30, y + 5), (x + 30, y + 20), (x + 10, y + 20)], close=True, dxfattribs={"layer": "BUILDINGS"})
        msp.add_text(f"P{i}{j}", dxfattribs={"layer": "TEXT", "height": 3, "insert": (x + 12, y + 22)})
msp.add_line((x0 - 10, y0 - 10), (x0 + 200, y0 - 10), dxfattribs={"layer": "ROADS"})
msp.add_circle((x0 + 90, y0 + 90), 8, dxfattribs={"layer": "ROADS"})
doc.saveas("sample.dxf")
print("ok")
