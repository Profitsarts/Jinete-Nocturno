import CoreMIDI
import Foundation

let target  = "IAC Driver Nocturn"
let cc      = UInt8(CommandLine.arguments.count > 1 ? UInt8(CommandLine.arguments[1])! : 23)
let seconds = CommandLine.arguments.count > 2 ? Double(CommandLine.arguments[2])! : 25.0

func name(_ o: MIDIObjectRef) -> String {
    var v: Unmanaged<CFString>?
    if MIDIObjectGetStringProperty(o, kMIDIPropertyDisplayName, &v) == noErr, let v = v {
        return v.takeRetainedValue() as String
    }
    return "?"
}

var client = MIDIClientRef(); MIDIClientCreate("send" as CFString, nil, nil, &client)
var port = MIDIPortRef();     MIDIOutputPortCreate(client, "out" as CFString, &port)

var dest: MIDIEndpointRef? = nil
for i in 0..<MIDIGetNumberOfDestinations() {
    let d = MIDIGetDestination(i)
    if name(d) == target { dest = d }
}
guard let dst = dest else { print("no encuentro la salida '\(target)'"); exit(1) }

print("enviando CC \(cc) en canal 1 hacia '\(target)' durante \(Int(seconds)) s")
fflush(stdout)

let end = Date().addingTimeInterval(seconds)
var v: UInt8 = 0
var up = true
while Date() < end {
    var pkt = MIDIPacketList()
    let p = MIDIPacketListInit(&pkt)
    var bytes: [UInt8] = [0xB0, cc, v]
    _ = MIDIPacketListAdd(&pkt, 1024, p, 0, 3, &bytes)
    MIDISend(port, dst, &pkt)
    if up { v += 4; if v >= 124 { up = false } } else { v -= 4; if v <= 2 { up = true } }
    usleep(40000)
}
print("fin del envío")
