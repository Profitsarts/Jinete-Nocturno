def lin(c):
    c = c/255.0 if c > 1 else c
    return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
def lum(rgb):
    r,g,b = [lin(v) for v in rgb]
    return 0.2126*r + 0.7152*g + 0.0722*b
def ratio(a,b):
    la,lb = lum(a), lum(b)
    hi,lo = max(la,lb), min(la,lb)
    return (hi+0.05)/(lo+0.05)
def hexof(rgb):
    return "#%02X%02X%02X" % tuple(int(round(v*255)) if v<=1 else int(v) for v in rgb)

BG_OLD = (0.878431,0.878431,0.878431)
RED_OLD = (0.792156862745098,0.062745098039216,0.062745098039216)
GRN_OLD = (0.047058823529412,0.643137254901961,0.047058823529412)
TXT_DEFAULT = (0.6,0.6,0.6)   # gris por defecto de textbutton, aproximado

print("=== ESTADO ACTUAL ===")
print(f"  fondo botón {hexof(BG_OLD)}")
for name,c in (("texto gris por defecto",TXT_DEFAULT),("rojo estado",RED_OLD),("verde estado",GRN_OLD)):
    r = ratio(c, BG_OLD)
    print(f"  {name:24s} {hexof(c)}  ratio {r:5.2f}:1  AA normal {'PASA' if r>=4.5 else 'FALLA'}")

print("\n=== CANDIDATOS ===")
cands = {
 "texto botón #1A1A1A": (0.10196,0.10196,0.10196),
 "rojo  #8E1116": (0.5569,0.0667,0.0863),
 "rojo  #A31414": (0.6392,0.0784,0.0784),
 "verde #0F5F23": (0.0588,0.3725,0.1373),
 "verde #14682A": (0.0784,0.4078,0.1647),
}
for name,c in cands.items():
    r = ratio(c, BG_OLD)
    print(f"  {name:22s} ratio {r:5.2f}:1  AA normal {'PASA' if r>=4.5 else 'FALLA'}  AAA {'PASA' if r>=7 else '-'}")
