import CoreMIDI
import Foundation

let target  = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "IAC Driver Nocturn"
let seconds = CommandLine.arguments.count > 2 ? Double(CommandLine.arguments[2])! : 90.0
let t0 = Date()

func name(_ o: MIDIObjectRef) -> String {
    var v: Unmanaged<CFString>?
    if MIDIObjectGetStringProperty(o, kMIDIPropertyDisplayName, &v) == noErr, let v = v {
        return v.takeRetainedValue() as String
    }
    return "?"
}

var client = MIDIClientRef(); MIDIClientCreate("mon" as CFString, nil, nil, &client)
var port = MIDIPortRef()
MIDIInputPortCreateWithBlock(client, "in" as CFString, &port) { pktList, _ in
    for p in pktList.unsafeSequence() {
        var b = [UInt8]()
        withUnsafeBytes(of: p.pointee.data) { raw in
            for k in 0..<Int(p.pointee.length) { b.append(raw[k]) }
        }
        var i = 0
        while i + 2 < b.count {
            let st = b[i]
            if st & 0xF0 == 0xB0 {
                let dt = Date().timeIntervalSince(t0)
                print(String(format: "%6.2fs  cc %3d  val %3d", dt, b[i+1], b[i+2]))
            }
            i += 3
        }
        fflush(stdout)
    }
}

var found = false
for i in 0..<MIDIGetNumberOfSources() where name(MIDIGetSource(i)) == target {
    MIDIPortConnectSource(port, MIDIGetSource(i), nil); found = true
}
guard found else { print("no encuentro '\(target)'"); exit(1) }
print("escuchando '\(target)' durante \(Int(seconds)) s")
fflush(stdout)
RunLoop.current.run(until: Date().addingTimeInterval(seconds))
print("fin")
