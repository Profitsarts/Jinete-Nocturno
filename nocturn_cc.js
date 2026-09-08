// nocturn_cc.js — Novation Nocturn -> generic MIDI CC, with encoder banks.
// Used by "Nocturn Generic MIDI CC.amxd" (Max for Live).
// Talks to the 11nocturn external by 11OLSEN.DE. No Live API, no fixed mapping.
//
// Edit the CONFIG block below and save: autowatch reloads it live.

autowatch = 1;
inlets  = 1;
outlets = 6;
// 0 = raw MIDI bytes  -> iter -> midiout
// 1 = [addr val]      -> prepend send -> 11nocturn
// 2 = link state      -> status lamp
// 3 = [cc val]        -> sprintf -> activity readout
// 4 = bank            -> tab
// 5 = [col row val]   -> matrixctrl

// ------------------------------------------------------------------ CONFIG --
var CHANNEL      = 1;    // MIDI channel, 1-16

// Base CC of encoders 1-8, one entry per bank. Bank 1 stays at 20 so existing
// mappings keep working. Add or remove entries to change the number of banks.
var CC_ENCODER_BANKS = [20, 46, 54, 62];

var CC_SPEEDDIAL = 28;   // speed dial, the same in every bank
var CC_FADER     = 29;   // crossfader, the same in every bank
var CC_BUTTON    = 30;   // buttons 1-16 -> CC 30..45, the same in every bank

var BUTTON_MODE  = 1;    // default for every button: 1 = toggle, 0 = momentary

// Per-button override, buttons 1-16. 1 = toggle, 0 = momentary,
// -1 = follow BUTTON_MODE. The 16 cells on the device face edit this, and the
// result is written to SETTINGS_FILE so it survives across sets.
var BUTTON_MODES = [-1, -1, -1, -1,
                    -1, -1, -1, -1,
                    -1, -1, -1, -1,
                    -1, -1, -1, -1];

var ACCEL        = 1;    // 1 = speed sensitive encoder steps, 0 = always 1 step
var RING_MODE    = 64;   // 0 from min, 16 from max, 32 from mid single,
                         // 48 from mid both, 64 single dot, 80 single dot inverted
var BRIGHTNESS   = 127;  // ONLY 127 (full), 126 (half) or 0 (LEDs off).
                         // Address 0 is a command byte, not a level. Any other
                         // value leaves the LEDs dark.
var LED_FEEDBACK = 1;    // 1 = rings and button LEDs follow the internal value
var START_VALUE  = 64;   // initial value of every encoder, 0-127
var GREET        = 1;    // 1 = flash every LED once when the hardware wakes up

// Where the button modes are stored. Absolute path. Change it if you move the
// device folder. Leave it empty to disable saving.
var SETTINGS_FILE = "/Users/condres/Muzik/Ableton/User Library/Presets/" +
                    "MIDI Effects/Max MIDI Effect/Nocturn Generic MIDI CC/" +
                    "nocturn_settings.json";
// ---------------------------------------------------------------------------

// hardware addresses of the 11nocturn "send" message, read off the help patch
var ADDR_BRIGHT    = 0;
var ADDR_RING_VAL  = 64;   // 64..71 encoders 1-8
var ADDR_RING_MODE = 72;   // 72..79 encoders 1-8
var ADDR_SD_VAL    = 80;   // speed dial ring value
var ADDR_SD_MODE   = 81;   // speed dial ring mode
var ADDR_BTN_LED   = 112;  // 112..127 buttons 1-16

var NENC  = 8;    // banked encoders
var NBTN  = 16;
var NBANK = CC_ENCODER_BANKS.length;

var curBank  = 0;
var encVal   = [];
var sdVal    = START_VALUE;
var faderVal = -1;
var half     = newArray(NENC + 1, 0);
var lastDir  = newArray(NENC + 1, 0);
var lastTime = newArray(NENC + 1, 0);
var btn      = newArray(NBTN, 0);

// Set once the patcher starts being torn down. The 11nocturn external has a
// race between its USB reader thread and its destructor: anything we send
// during teardown can land on a freed handle and take Live down with it.
var shuttingDown = 0;
var loadingUI    = 0;

for (var b0 = 0; b0 < NBANK; b0++) { encVal[b0] = newArray(NENC, START_VALUE); }

function newArray(n, v) {
    var a = [];
    for (var i = 0; i < n; i++) { a[i] = v; }
    return a;
}

// -------------------------------------------------------------- encoder in --
// Relative protocol: 1..4 clockwise, 127..124 counter-clockwise.
// The smallest tick (1 / 127) is half a detent, so it takes two of them.
// Anything else repeats the last direction, as the original help patch does.
function encoder(idx, raw) {
    idx = parseInt(idx);
    raw = parseInt(raw);
    if (idx < 0 || idx > NENC) { return; }

    var dir = 0;
    var whole = true;
    if (raw >= 1 && raw <= 4)          { dir =  1; whole = (raw > 1); }
    else if (raw >= 124 && raw <= 127) { dir = -1; whole = (raw < 127); }
    else                               { dir = lastDir[idx]; }
    if (dir === 0) { return; }

    if (dir !== lastDir[idx]) { half[idx] = 0; }
    lastDir[idx] = dir;

    if (!whole) {
        half[idx] += 1;
        if (half[idx] < 2) { return; }
    }
    half[idx] = 0;

    setEncoder(idx, valueOf(idx) + dir * stepSize(idx));
}

// Acceleration curve copied from the 11Olsen help patch:
// breakpoints (0, 1) (18.721461, 1.609272, curve 0.15) (60, 9.377483, curve 0.45)
// over x = 60 - milliseconds since the previous step, clipped to 0..60.
function stepSize(idx) {
    var now = (new Date()).getTime();
    var dt  = now - lastTime[idx];
    lastTime[idx] = now;
    if (!ACCEL) { return 1; }
    if (dt > 60) { dt = 60; }
    if (dt < 0)  { dt = 0; }
    var s = Math.round(curve(60 - dt));
    return s < 1 ? 1 : s;
}

function curve(x) {
    if (x <= 0)  { return 1.0; }
    if (x >= 60) { return 9.377483; }
    if (x <= 18.721461) {
        return segment(x, 0, 1.0, 18.721461, 1.609272, 0.15);
    }
    return segment(x, 18.721461, 1.609272, 60, 9.377483, 0.45);
}

function segment(x, x0, y0, x1, y1, c) {
    var t = (x - x0) / (x1 - x0);
    var k = Math.log(0.5) / Math.log(c);   // c = 0.5 gives a straight line
    return y0 + (y1 - y0) * Math.pow(t, k);
}

function valueOf(idx) {
    return (idx === NENC) ? sdVal : encVal[curBank][idx];
}

function setEncoder(idx, v) {
    v = clip127(v);
    if (v === valueOf(idx)) { return; }
    if (idx === NENC) {
        sdVal = v;
        sendCC(CC_SPEEDDIAL, v);
        led(ADDR_SD_VAL, v);
    } else {
        encVal[curBank][idx] = v;
        sendCC(CC_ENCODER_BANKS[curBank] + idx, v);
        led(ADDR_RING_VAL + idx, v);
    }
}

// ---------------------------------------------------------------- banks in --
// Called by the tab on the device face. Each bank keeps its own eight values,
// so switching repaints the rings instead of jumping the mapped parameters.
function bank(n) {
    n = parseInt(n);
    if (isNaN(n) || n < 0 || n >= NBANK) { return; }
    if (n === curBank) { return; }
    curBank = n;
    refreshRings();
}

// ---------------------------------------------------------------- other in --
function fader(v) {
    v = clip127(parseInt(v));
    if (v === faderVal) { return; }
    faderVal = v;
    sendCC(CC_FADER, v);
}

function button(idx, v) {
    idx = parseInt(idx);
    v   = parseInt(v);
    if (idx < 0 || idx >= NBTN) { return; }

    if (modeOf(idx)) {
        if (v <= 0) { return; }             // act on press only
        btn[idx] = btn[idx] ? 0 : 1;
    } else {
        btn[idx] = (v > 0) ? 1 : 0;
    }
    sendCC(CC_BUTTON + idx, btn[idx] ? 127 : 0);
    buttonLed(idx, btn[idx]);
}

// 1 = toggle, 0 = momentary. Falls back to BUTTON_MODE when the per-button
// entry is anything other than 0 or 1.
function modeOf(idx) {
    var m = (idx >= 0 && idx < BUTTON_MODES.length) ? BUTTON_MODES[idx] : -1;
    if (m === 0 || m === 1) { return m; }
    return BUTTON_MODE ? 1 : 0;
}

// From the 16 cells on the device face. Lit = toggle, dark = momentary.
//
// Physical layout, measured by pressing every button and reading the CC that
// came out. The Nocturn splits its buttons into two blocks of 4 x 2, with the
// logo in between, and the indices run across both blocks per row:
//
//     row 0:  0  1  2  3  |logo|  4  5  6  7
//     row 1:  8  9 10 11  |logo| 12 13 14 15
//
// All 16 respond. Nothing is missing.
function btnmode(idx, val) {
    if (loadingUI) { return; }
    idx = parseInt(idx);
    if (idx < 0 || idx >= NBTN) { return; }
    BUTTON_MODES[idx] = parseInt(val) ? 1 : 0;
    saveSettings();
}

function touch(idx, v) {
    // Touch sensors are read but unused. Hook your own behaviour here.
}

function link(state) {
    if (shuttingDown) { return; }
    state = parseInt(state);
    outlet(2, state);
    if (state === 1) { initOnce(); }
}

// Called from freebang and closebang, before the external is freed.
function shutdown() {
    shuttingDown = 1;
    if (greetTask !== null) { greetTask.cancel(); }
}

// ------------------------------------------------------------------ output --
// Raw status and data bytes, not ctlout. In Max for Live only midiout is
// documented to feed the track's MIDI chain, so we build the CC by hand.
function sendCC(cc, val) {
    if (shuttingDown) { return; }
    if (cc < 0 || cc > 127) { return; }
    var ch = CHANNEL;
    if (ch < 1)  { ch = 1; }
    if (ch > 16) { ch = 16; }
    val = clip127(val);
    outlet(0, 176 + (ch - 1), cc, val);
    outlet(3, cc, val);
}

function led(addr, val) {
    if (shuttingDown || !LED_FEEDBACK) { return; }
    outlet(1, addr, clip127(val));
}

function buttonLed(idx, on) {
    led(ADDR_BTN_LED + idx, on ? 127 : 0);
}

function clip127(v) {
    v = Math.round(v);
    if (isNaN(v) || v < 0) { return 0; }
    return (v > 127) ? 127 : v;
}

// ----------------------------------------------------------------- control --
// The external can report "connected" while its USB claim is still failing, and
// it then flaps between states. Without this cooldown each flap fires a full
// init, which floods Live's log with write errors. Do not remove it.
var INIT_COOLDOWN = 3000;
var lastInit  = 0;
var greetTask = null;

function initOnce() {
    if (shuttingDown) { return; }
    if ((new Date()).getTime() - lastInit < INIT_COOLDOWN) { return; }
    init();
}

// Sent once the device is loaded, and again whenever the hardware reconnects.
function init() {
    if (shuttingDown) { return; }
    lastInit = (new Date()).getTime();
    loadSettings();
    pushUI();
    outlet(1, ADDR_BRIGHT, brightness());
    ringModes();
    if (GREET) { greet(); } else { refresh(); }
}

// Address 0 takes a command, not a level. 127 full, 126 half, 0 off.
function brightness() {
    return (BRIGHTNESS === 126 || BRIGHTNESS === 0) ? BRIGHTNESS : 127;
}

function ringModes() {
    for (var i = 0; i < NENC; i++) { led(ADDR_RING_MODE + i, RING_MODE); }
    led(ADDR_SD_MODE, RING_MODE);
}

// Paint the device face from the values held here, without echoing back.
function pushUI() {
    loadingUI = 1;
    outlet(4, "set", curBank);
    for (var i = 0; i < NBTN; i++) { outlet(5, i, "set", modeOf(i)); }
    loadingUI = 0;
}

// Fill every ring and light every button for half a second, then settle.
// Without this the device wakes up showing almost nothing and looks dead.
function greet() {
    if (shuttingDown) { return; }
    if (!LED_FEEDBACK) { refresh(); return; }
    for (var i = 0; i < NENC; i++) {
        outlet(1, ADDR_RING_MODE + i, 0);   // 0 = fill from the minimum
        outlet(1, ADDR_RING_VAL + i, 127);
    }
    outlet(1, ADDR_SD_MODE, 0);
    outlet(1, ADDR_SD_VAL, 127);
    for (var b = 0; b < NBTN; b++) { outlet(1, ADDR_BTN_LED + b, 127); }
    if (greetTask === null) { greetTask = new Task(settle, this); }
    greetTask.cancel();
    greetTask.schedule(600);
}

function settle() {
    if (shuttingDown) { return; }
    ringModes();
    refresh();
}

function refreshRings() {
    for (var i = 0; i < NENC; i++) { led(ADDR_RING_VAL + i, encVal[curBank][i]); }
    led(ADDR_SD_VAL, sdVal);
}

// Repaint every LED from the values held here.
function refresh() {
    refreshRings();
    for (var b = 0; b < NBTN; b++) { buttonLed(b, btn[b]); }
}

// Turn every LED off without changing the stored values.
function ledsoff() {
    if (shuttingDown) { return; }
    for (var i = 0; i < NENC; i++) { outlet(1, ADDR_RING_VAL + i, 0); }
    outlet(1, ADDR_SD_VAL, 0);
    for (var b = 0; b < NBTN; b++) { outlet(1, ADDR_BTN_LED + b, 0); }
}

// Zero every encoder and button in every bank, send the CCs, repaint.
function reset() {
    for (var k = 0; k < NBANK; k++) {
        for (var i = 0; i < NENC; i++) {
            encVal[k][i] = START_VALUE;
            sendCC(CC_ENCODER_BANKS[k] + i, START_VALUE);
        }
    }
    sdVal = START_VALUE;
    sendCC(CC_SPEEDDIAL, START_VALUE);
    for (var b = 0; b < NBTN; b++) {
        btn[b] = 0;
        sendCC(CC_BUTTON + b, 0);
    }
    refresh();
}

// -------------------------------------------------------------- settings ----
// Button modes live in a JSON file next to the device, not in the Live set, so
// one setup applies to every project. A failure here must never break the
// device: worst case the defaults from the CONFIG block above stay in force.
function loadSettings() {
    if (!SETTINGS_FILE.length) { return; }
    try {
        var d = new Dict();
        d.import_json(SETTINGS_FILE);
        var m = d.get("button_modes");
        if (m && m.length === NBTN) {
            for (var i = 0; i < NBTN; i++) {
                var v = parseInt(m[i]);
                BUTTON_MODES[i] = (v === 0 || v === 1) ? v : -1;
            }
        }
    } catch (e) {
        // no settings file yet, or it is unreadable. Defaults stand.
    }
}

function saveSettings() {
    if (!SETTINGS_FILE.length) { return; }
    try {
        var d = new Dict();
        d.set("button_modes", BUTTON_MODES);
        d.export_json(SETTINGS_FILE);
    } catch (e) {
        post("nocturn_cc: could not write " + SETTINGS_FILE + "\n");
    }
}

// Print the current map to the Max window.
function ccmap() {
    post("Nocturn CC map, MIDI channel " + CHANNEL + "\n");
    for (var k = 0; k < NBANK; k++) {
        post("  bank " + (k + 1) + " encoders 1-8 : CC " + CC_ENCODER_BANKS[k] +
             "-" + (CC_ENCODER_BANKS[k] + 7) +
             (k === curBank ? "   <- active\n" : "\n"));
    }
    post("  speed dial   : CC " + CC_SPEEDDIAL + "\n");
    post("  crossfader   : CC " + CC_FADER + "\n");
    post("  buttons 1-16 : CC " + CC_BUTTON + "-" + (CC_BUTTON + 15) + "\n");
    var line = "  button modes : ";
    for (var i = 0; i < NBTN; i++) {
        line += (i + 1) + "=" + (modeOf(i) ? "tog" : "mom") + " ";
    }
    post(line + "\n");
}
