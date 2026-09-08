#!/usr/bin/env python3
"""Build "Nocturn Generic MIDI CC.amxd" from the factory Max MIDI Effect template.

Two design notes worth keeping:

* Every "state 1" sent to the 11nocturn external is a chance to crash Live. The
  external calls libusb_close inside nocturn_start and dereferences null when a
  previous handle is stale. So this patch sends it once per explicit request.
* textbutton's default label colour is a light grey that lands at 2.16:1 on the
  grey button face, well under the WCAG AA floor of 4.5:1. Every label colour
  here is set explicitly and measured.
"""
import json, struct, sys, copy

TPL, OUT = sys.argv[1], sys.argv[2]

def read_amxd(path):
    d = open(path, 'rb').read(); off, chunks = 0, {}
    while off + 8 <= len(d):
        typ = d[off:off+4]; sz = struct.unpack('<I', d[off+4:off+8])[0]
        chunks[typ] = d[off+8:off+8+sz]; off += 8 + sz
    return chunks

def json_of(ptch):
    start = ptch.index(b'{'); depth = 0; instr = False; esc = False
    for i in range(start, len(ptch)):
        c = ptch[i:i+1]
        if esc: esc = False; continue
        if instr:
            if c == b'\\': esc = True
            elif c == b'"': instr = False
            continue
        if c == b'"': instr = True
        elif c == b'{': depth += 1
        elif c == b'}':
            depth -= 1
            if depth == 0: return json.loads(ptch[start:i+1].decode('utf-8'))
    raise ValueError('no patcher json')

FONT = "Arial"
# measured against BTN_BG: text 13.18:1, red 5.96:1, green 5.93:1
BTN_BG = [0.878431, 0.878431, 0.878431, 1.0]
BTN_TX = [0.101961, 0.101961, 0.101961, 1.0]
RED    = [0.639216, 0.078431, 0.078431, 1.0]
GREEN  = [0.058824, 0.372549, 0.137255, 1.0]
# active tab: #5F97D6, dark text on it measures 5.71:1
TAB_ON = [0.372549, 0.592157, 0.839216, 1.0]
# Button cells: two shades of red on the top row, two of green on the bottom,
# like the hardware. Pale = toggle, vivid = momentary. Every pair measured
# against BTN_TX, and every one clears the WCAG AA floor of 4.5:1.
CELL_RED  = [0.909804, 0.458824, 0.419608, 1.0]   # #E8756B pale red    5.96:1
CELL_GRN  = [0.435294, 0.796078, 0.501961, 1.0]   # #6FCB80 pale green  8.73:1
CELL_REDV = [1.000000, 0.200000, 0.000000, 1.0]   # #FF3300 vivid red   4.75:1
CELL_GRNV = [0.000000, 0.831373, 0.000000, 1.0]   # #00D400 vivid green 8.63:1

boxes, lines, _ids = [], [], {}

def box(bid, maxclass, x, y, w, h, nin, nout, outtype=None, text=None,
        pres=None, extra=None):
    b = {"id": bid, "maxclass": maxclass, "numinlets": nin, "numoutlets": nout,
         "patching_rect": [float(x), float(y), float(w), float(h)]}
    if outtype is not None: b["outlettype"] = outtype
    if text is not None:    b["text"] = text
    if pres is not None:
        b["presentation"] = 1; b["presentation_rect"] = [float(v) for v in pres]
    if extra: b.update(extra)
    boxes.append({"box": b}); _ids[bid] = b
    return bid

def link(s, so, d, di):
    lines.append({"patchline": {"destination": [d, di], "source": [s, so]}})

def tbutton(bid, x, y, w, h, label, pres):
    return box(bid, "textbutton", x, y, w, h, 1, 3, ["", "", "int"],
               text=label, pres=pres,
               extra={"fontname": FONT, "fontsize": 11.0, "parameter_enable": 0,
                      "mode": 0, "rounded": 3.0,
                      "bgcolor": BTN_BG, "bgoncolor": BTN_BG,
                      "textcolor": BTN_TX, "textoncolor": BTN_TX,
                      "usebgoncolor": 1})

def label(bid, x, y, w, text, pres, size=10.0, face=0):
    return box(bid, "comment", x, y, w, 18, 1, 0, text=text, pres=pres,
               extra={"fontname": FONT, "fontsize": size, "fontface": face})

# ------------------------------------------------------------- device face --
# Live caps a device at 169 px tall. Six bands compete for it, so the spacing
# is laid out explicitly rather than eyeballed: 9 px between bands, 12 px side
# margins, and the mode caption kept 3 px from its cells so it reads as their
# label instead of as a seventh band.
M      = 12    # side margin
W      = 226   # usable width
GAP    = 9     # air between bands
Y_STAT, H_STAT = 6, 20
Y_BANK, H_BANK = Y_STAT + H_STAT + GAP, 20
Y_BTNS, H_BTNS = Y_BANK + H_BANK + GAP, 20
Y_CAP,  H_CAP  = Y_BTNS + H_BTNS + GAP, 10
Y_ROW0         = Y_CAP + H_CAP + 7   # padding-bottom under the caption
CELL, PITCH    = 15, 17
Y_ROW1         = Y_ROW0 + PITCH
Y_SEEN, H_SEEN = Y_ROW1 + CELL + GAP, 15

STAT = box("obj-stat", "textbutton", 20, 50, 200, 22, 1, 3, ["", "", "int"],
           text="waiting for Nocturn", pres=[M, Y_STAT, W, H_STAT],
           extra={"fontname": FONT, "fontsize": 11.0, "fontface": 1,
                  "parameter_enable": 0, "mode": 1, "ignoreclick": 1,
                  "rounded": 3.0, "texton": "Nocturn connected",
                  "textcolor": RED, "textoncolor": GREEN,
                  "bgcolor": BTN_BG, "bgoncolor": BTN_BG, "usebgoncolor": 1})

label("obj-lbank", 20, 80, 40, "bank", [M, Y_BANK + 2, 30, 16])
TAB = box("obj-tab", "tab", 70, 80, 180, 22, 1, 3, ["int", "", "int"],
          pres=[M + 34, Y_BANK, W - 34, H_BANK],
          extra={"fontname": FONT, "fontsize": 10.0, "fontface": 1,
                 "parameter_enable": 0,
                 "tabs": ["1", "2", "3", "4"],
                 "bgcolor": BTN_BG, "textcolor": BTN_TX,
                 "bgoncolor": TAB_ON, "textoncolor": BTN_TX})

BW = (W - 2 * 8) // 3        # three buttons, 8 px apart
BINIT = tbutton("obj-binit", 20, 112, 80, 22, "re-init",
                [M, Y_BTNS, BW, H_BTNS])
BOFF  = tbutton("obj-boff", 105, 112, 80, 22, "LEDs off",
                [M + BW + 8, Y_BTNS, BW, H_BTNS])
BSTOP = tbutton("obj-bstop", 190, 112, 80, 22, "stop USB",
                [M + 2 * (BW + 8), Y_BTNS, BW, H_BTNS])

label("obj-lmode", 20, 145, 240, "button mode   pale = toggle, vivid = momentary",
      [M, Y_CAP, W, H_CAP], size=9.0)

# The 16 buttons, laid out like the hardware: two blocks of 4 x 2 with the logo
# between them. Indices run across both blocks per row, measured on the unit:
#     row 0:  0 1 2 3 |logo|  4  5  6  7
#     row 1:  8 9 10 11|logo| 12 13 14 15
BLOCK = 3 * PITCH + CELL           # 66
LEFT_X, RIGHT_X = M, M + W - BLOCK
CELLS = []
for row in range(2):
    for blk, x0 in ((0, LEFT_X), (1, RIGHT_X)):
        for col in range(4):
            idx = blk * 4 + col + row * 8
            on  = CELL_RED  if row == 0 else CELL_GRN    # toggle
            off = CELL_REDV if row == 0 else CELL_GRNV   # momentary
            # Both rows read 1-8, like the two rows of controls on the unit.
            # A two digit label would be clipped in a 15 px cell, and texton
            # must match text or the label changes when the cell is toggled.
            lbl = str(blk * 4 + col + 1)
            cid = box("obj-cell%d" % idx, "textbutton",
                      40 + col * 40 + blk * 180, 380 + row * 30, 36, 20, 1, 3,
                      ["", "", "int"], text=lbl,
                      pres=[x0 + col * PITCH, Y_ROW0 + row * PITCH, CELL, CELL],
                      extra={"fontname": FONT, "fontsize": 8.0, "mode": 1,
                             "parameter_enable": 0, "rounded": 2.0,
                             "texton": lbl,
                             "bgcolor": off, "bgoncolor": on,
                             "textcolor": BTN_TX, "textoncolor": BTN_TX,
                             "usebgoncolor": 1})
            CELLS.append((idx, cid))
CELLS.sort()

LOGO_W = 81
LOGO_X = LEFT_X + BLOCK + ((RIGHT_X - LEFT_X - BLOCK) - LOGO_W) // 2
LOGO = box("obj-logo", "fpic", 620, 380, 90, 40, 1, 1, [""],
           pres=[LOGO_X, Y_ROW0, LOGO_W, CELL + PITCH],
           extra={"pic": "nocturn_logo.png", "autofit": 1, "embed": 0})

SEEN = label("obj-seen", 20, 190, 225, "no CC sent yet",
             [M, Y_SEEN, W, H_SEEN], size=11.0, face=1)

# --------------------------------------------------------------- start up --
DEV  = box("obj-dev",  "live.thisdevice", 320, 30, 120, 22, 1, 3,
           ["bang", "bang", "int"])
TRG1 = box("obj-trg1", "newobj", 320, 70, 60, 22, 1, 3,
           ["bang", "bang", "bang"], "t b b b")
MWIN = box("obj-mwin", "message", 470, 105, 85, 22, 2, 1, [""], "maxwindow 0")
DEL1 = box("obj-del1", "newobj", 320, 105, 70, 22, 2, 1, ["bang"], "del 1000")
TRG2 = box("obj-trg2", "newobj", 320, 140, 50, 22, 1, 2, ["bang", "bang"], "t b b")
MSTA = box("obj-msta", "message", 400, 175, 55, 22, 2, 1, [""], "state 1")
DEL2 = box("obj-del2", "newobj", 320, 175, 60, 22, 2, 1, ["bang"], "del 400")
MINI = box("obj-mini", "message", 320, 210, 40, 22, 2, 1, [""], "init")
MOFF = box("obj-moff", "message", 200, 210, 60, 22, 2, 1, [""], "ledsoff")

# ---------------------------------------------------------------- teardown --
# Live crashes in the external's own libusb_release_interface if "state 0"
# arrives twice. Pressing "stop USB" and then deleting the device did exactly
# that: one stop by hand, a second from closebang. This gate lets the first
# stop through and then shuts, so the release can only ever happen once.
# It reopens on load and on re-init.
FREEB = box("obj-freeb", "newobj", 40, 250, 70, 22, 1, 1, ["bang"], "freebang")
CLOSB = box("obj-closb", "newobj", 120, 250, 75, 22, 1, 1, ["bang"], "closebang")
TRG3  = box("obj-trg3", "newobj", 40, 285, 50, 22, 1, 2, ["bang", "bang"], "t b b")
MSHUT = box("obj-mshut", "message", 120, 320, 70, 22, 2, 1, [""], "shutdown")
TRG4  = box("obj-trg4", "newobj", 40, 320, 50, 22, 1, 2, ["bang", "bang"], "t b b")
MOPEN = box("obj-mopen", "message", 210, 320, 30, 22, 2, 1, [""], "1")
MSHUT2 = box("obj-mclose", "message", 105, 355, 30, 22, 2, 1, [""], "0")
GATE  = box("obj-gate", "newobj", 40, 390, 60, 22, 2, 1, [""], "gate")
MST0  = box("obj-mst0", "message", 40, 425, 55, 22, 2, 1, [""], "state 0")

# ------------------------------------------------------------ hardware -> js
NOC = box("obj-noc", "newobj", 40, 480, 560, 22, 1, 6,
          ["list", "int", "list", "list", "list", "int"], "11nocturn",
          extra={"fontface": 1, "fontname": FONT, "fontsize": 12.0,
                 "color": [0.811765, 0.494118, 0.113725, 1.0]})
PB = box("obj-pb", "newobj", 40,  530, 100, 22, 2, 1, [""], "prepend button")
PF = box("obj-pf", "newobj", 150, 530, 95,  22, 2, 1, [""], "prepend fader")
PE = box("obj-pe", "newobj", 255, 530, 110, 22, 2, 1, [""], "prepend encoder")
PT = box("obj-pt", "newobj", 375, 530, 95,  22, 2, 1, [""], "prepend touch")
PL = box("obj-pl", "newobj", 480, 530, 90,  22, 2, 1, [""], "prepend link")
# Outlet 4 is undocumented in the 11Olsen help patch. Wire it so whatever it
# carries can be identified rather than guessed at.
PAX = box("obj-pax", "newobj", 580, 560, 90, 22, 2, 1, [""], "prepend aux")
PBK = box("obj-pbk", "newobj", 620, 480, 90, 22, 2, 1, [""], "prepend bank")
# one prepend per cell so js learns which button was clicked
PMDS = []
for idx, cid in CELLS:
    PMDS.append(box("obj-pmd%d" % idx, "newobj",
                    40 + (idx % 8) * 90, 440 + (idx // 8) * 26, 85, 20, 2, 1,
                    [""], "prepend btnmode %d" % idx))
ROUTE = box("obj-route", "newobj", 250, 700, 340, 22, 1, 17,
            [""] * 17, "route " + " ".join(str(i) for i in range(16)))

JS   = box("obj-js", "newobj", 40, 580, 140, 22, 1, 6,
           ["", "", "", "", "", ""], "js nocturn_cc.js")
ITER = box("obj-iter", "newobj", 40, 620, 40, 22, 1, 1, [""], "iter")
MOUT = box("obj-mout", "newobj", 40, 660, 60, 22, 1, 0, None, "midiout")
PS   = box("obj-ps", "newobj", 250, 620, 90, 22, 2, 1, [""], "prepend send")
SPR  = box("obj-spr", "newobj", 150, 660, 190, 22, 2, 1, [""],
           "sprintf set sent CC %ld = %ld")

label("obj-note", 40, 700, 560,
      "midiout feeds this track's MIDI chain. Put this device alone on a MIDI "
      "track with no instrument and route that track to an IAC bus.", None)

# ------------------------------------------------------------------ wiring --
link(DEV, 0, TRG1, 0); link(BINIT, 0, TRG1, 0)
link(TRG1, 2, MOPEN, 0); link(MOPEN, 0, GATE, 0)   # arm the one-shot release
link(TRG1, 1, MWIN, 0); link(MWIN, 0, NOC, 0)
link(TRG1, 0, DEL1, 0); link(DEL1, 0, TRG2, 0)
link(TRG2, 1, MSTA, 0); link(MSTA, 0, NOC, 0)
link(TRG2, 0, DEL2, 0); link(DEL2, 0, MINI, 0); link(MINI, 0, JS, 0)

link(BOFF, 0, MOFF, 0); link(MOFF, 0, JS, 0)

link(BSTOP, 0, TRG3, 0); link(FREEB, 0, TRG3, 0); link(CLOSB, 0, TRG3, 0)
link(TRG3, 1, MSHUT, 0); link(MSHUT, 0, JS, 0)
link(TRG3, 0, TRG4, 0)
link(TRG4, 1, GATE, 1)                 # right outlet first: try to pass
link(TRG4, 0, MSHUT2, 0); link(MSHUT2, 0, GATE, 0)   # then latch it shut
link(GATE, 0, MST0, 0);  link(MST0, 0, NOC, 0)

link(NOC, 0, PB, 0); link(PB, 0, JS, 0)
link(NOC, 1, PF, 0); link(PF, 0, JS, 0)
link(NOC, 2, PE, 0); link(PE, 0, JS, 0)
link(NOC, 3, PT, 0); link(PT, 0, JS, 0)
link(NOC, 4, PAX, 0); link(PAX, 0, JS, 0)
link(NOC, 5, PL, 0); link(PL, 0, JS, 0)

link(TAB, 0, PBK, 0); link(PBK, 0, JS, 0)
for n, (idx, cid) in enumerate(CELLS):
    link(cid, 0, PMDS[n], 0)
    link(PMDS[n], 0, JS, 0)
    link(ROUTE, idx, cid, 0)


link(JS, 0, ITER, 0); link(ITER, 0, MOUT, 0)
link(JS, 1, PS, 0);   link(PS, 0, NOC, 0)
link(JS, 2, STAT, 0)
link(JS, 3, SPR, 0);  link(SPR, 0, SEEN, 0)
link(JS, 4, TAB, 0)
link(JS, 5, ROUTE, 0)

# ------------------------------------------------------------------ output --
p = copy.deepcopy(json_of(read_amxd(TPL)[b'ptch'])['patcher'])
p['boxes'] = boxes; p['lines'] = lines
p['rect'] = [80.0, 100.0, 760.0, 800.0]
p['openrect'] = [0.0, 0.0, 250.0, float(Y_SEEN + H_SEEN + 3)]
p['openinpresentation'] = 1
p['title'] = "Nocturn Generic MIDI CC"
p['description'] = "Novation Nocturn as a free MIDI CC controller"
p['digest'] = "Nocturn -> generic MIDI CC"
p['tags'] = "nocturn midi cc controller"
p['default_fontname'] = FONT
p['dependency_cache'] = []

payload = json.dumps({"patcher": p}, indent=1).replace('\n', '\r\n').encode('utf-8') + b'\n\x00'
def chunk(t, d): return t + struct.pack('<I', len(d)) + d
open(OUT, 'wb').write(chunk(b'ampf', b'mmmm') + chunk(b'meta', b'\x00'*4) + chunk(b'ptch', payload))
print(f"wrote {len(boxes)} boxes, {len(lines)} lines")
