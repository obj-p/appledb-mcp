import Foundation

enum CycleDetector {

    struct CyclePath {
        let nodes: [String] // ["0xABC (ClassA)", "0xDEF (ClassB)", "0xABC (ClassA)"]
    }

    /// Detect retain cycles starting from the given address.
    /// Uses BFS to follow strong (object) references.
    static func detect(from startAddress: UInt, maxDepth: Int = 10) -> [CyclePath] {
        var visited: Set<UInt> = []
        var cycles: [CyclePath] = []
        var queue: [(address: UInt, path: [String])] = []

        let startDesc = describeAddress(startAddress)
        queue.append((startAddress, [startDesc]))
        visited.insert(startAddress)

        var totalVisited = 0
        let maxVisited = 100_000

        while !queue.isEmpty {
            let (addr, path) = queue.removeFirst()
            totalVisited += 1
            if totalVisited > maxVisited { break }
            if path.count > maxDepth + 1 { continue }

            let refs = ObjectIntrospector.outboundReferences(address: addr)

            for ref in refs {
                guard let addrStr = ref["address"] as? String,
                      let refAddr = UInt(addrStr.dropFirst(2), radix: 16) else { continue }
                guard refAddr != 0 else { continue }

                let refDesc = "\(addrStr) (\(ref["class"] as? String ?? "?"))"

                if refAddr == startAddress {
                    // Found a cycle back to start
                    cycles.append(CyclePath(nodes: path + [refDesc]))
                } else if !visited.contains(refAddr) {
                    visited.insert(refAddr)
                    queue.append((refAddr, path + [refDesc]))
                }
            }
        }

        return cycles
    }

    private static func describeAddress(_ address: UInt) -> String {
        guard let ptr = UnsafeRawPointer(bitPattern: address) else {
            return String(format: "0x%lx (?)", address)
        }
        let obj = unsafeBitCast(ptr, to: AnyObject.self)
        let cls: AnyClass? = object_getClass(obj)
        let name = cls.map { String(cString: class_getName($0)) } ?? "?"
        return String(format: "0x%lx (%@)", address, name as NSString)
    }
}
