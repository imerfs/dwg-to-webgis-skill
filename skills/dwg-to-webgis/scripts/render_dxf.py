"""Render a DXF to PNG (whole drawing, or one/some layers) so it can be inspected visually.

usage: python -I render_dxf.py in.dxf out.png [--layers L1,L2] [--dpi 150] [--list]
"""
import argparse
import sys

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

p = argparse.ArgumentParser()
p.add_argument("dxf")
p.add_argument("png", nargs="?")
p.add_argument("--layers", default="")
p.add_argument("--dpi", type=int, default=150)
p.add_argument("--list", action="store_true", help="print layer table and entity counts, then exit")
a = p.parse_args()

doc = ezdxf.readfile(a.dxf)
msp = doc.modelspace()

if a.list:
    from collections import Counter
    counts = Counter((e.dxf.layer, e.dxftype()) for e in msp)
    layers = {l.dxf.name: l for l in doc.layers}
    print("INSUNITS:", doc.header.get("$INSUNITS"), "EXTMIN:", doc.header.get("$EXTMIN"), "EXTMAX:", doc.header.get("$EXTMAX"))
    for name, l in sorted(layers.items()):
        kinds = {t: n for (ln, t), n in counts.items() if ln == name}
        print(f"{name!r:24} aci={l.dxf.color:<4} off={l.is_off()} frozen={l.is_frozen()} {kinds}")
    sys.exit(0)

wanted = {s.strip() for s in a.layers.split(",") if s.strip()}
if wanted:
    for layer in doc.layers:
        if layer.dxf.name not in wanted:
            layer.off()

fig = plt.figure(figsize=(12, 9))
ax = fig.add_axes([0, 0, 1, 1])
ctx = RenderContext(doc)
Frontend(ctx, MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
fig.savefig(a.png, dpi=a.dpi, facecolor="white")
print("saved", a.png)
