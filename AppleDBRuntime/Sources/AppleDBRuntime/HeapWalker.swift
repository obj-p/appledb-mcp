import Foundation
import Darwin
import ObjectiveC

struct HeapEntry {
    let address: UInt
    let size: UInt
    let className: String
}

/// Context passed through the C callback via UnsafeMutableRawPointer
private class HeapWalkContext {
    var entries: [HeapEntry] = []
    var count: Int = 0
    let maxEntries: Int

    init(maxEntries: Int = 10_000_000) {
        self.maxEntries = maxEntries
    }
}

enum HeapWalker {

    /// Walk all malloc zones and collect ObjC/Swift heap objects.
    static func walkHeap(classFilter: String? = nil, maxResults: Int = 0) -> [HeapEntry] {
        var zoneCount: UInt32 = 0
        var zones: UnsafeMutablePointer<vm_address_t>?

        let result = malloc_get_all_zones(mach_task_self_, nil, &zones, &zoneCount)
        guard result == KERN_SUCCESS, let zones = zones else {
            return []
        }

        var entries: [HeapEntry] = []
        let limit = maxResults > 0 ? maxResults : Int.max

        for i in 0..<Int(zoneCount) {
            let zoneAddr = zones[i]
            guard let zone = UnsafeMutablePointer<malloc_zone_t>(bitPattern: zoneAddr) else { continue }

            guard let introspect = zone.pointee.introspect,
                  let enumerator = introspect.pointee.enumerator else {
                continue
            }

            // Use the enumerator to walk allocations in this zone.
            // We call it with a recording callback that collects entries.
            let ctx = HeapWalkContext(maxEntries: 10_000_000)
            let ctxPtr = Unmanaged.passUnretained(ctx).toOpaque()

            _ = enumerator(
                mach_task_self_,
                ctxPtr,
                UInt32(MALLOC_PTR_IN_USE_RANGE_TYPE),
                zoneAddr,
                nil, // memory reader — nil for in-process
                heapEnumerationCallback
            )

            for entry in ctx.entries {
                if let filter = classFilter {
                    if entry.className == filter || entry.className.hasSuffix(".\(filter)") {
                        entries.append(entry)
                    }
                } else {
                    entries.append(entry)
                }
                if entries.count >= limit { return entries }
            }
        }

        return entries
    }
}

/// C callback for malloc zone enumeration.
/// Called once per allocation range in the zone.
private func heapEnumerationCallback(
    _ task: mach_port_t,
    _ context: UnsafeMutableRawPointer?,
    _ type: UInt32,
    _ ranges: UnsafeMutablePointer<vm_range_t>?,
    _ rangeCount: UInt32
) {
    guard let context = context, let ranges = ranges else { return }
    let ctx = Unmanaged<HeapWalkContext>.fromOpaque(context).takeUnretainedValue()

    for i in 0..<Int(rangeCount) {
        if ctx.count >= ctx.maxEntries { return }

        let range = ranges[i]
        let addr = range.address
        let size = range.size

        // Skip allocations too small to be ObjC objects (isa + refcount = 16 bytes minimum)
        guard size >= 16 else { continue }

        // Try to read the isa pointer (first pointer-sized bytes)
        let ptr = UnsafeRawPointer(bitPattern: addr)
        guard let ptr = ptr else { continue }

        // Safely read the potential isa pointer
        let isaCandidate = ptr.load(as: UInt.self)
        guard isaCandidate != 0 else { continue }

        // Validate: is this a real ObjC class?
        let cls: AnyClass? = unsafeBitCast(isaCandidate, to: AnyClass?.self)
        guard let cls = cls else { continue }

        // class_getName returns a C string — if it crashes or returns garbage, skip
        let namePtr = class_getName(cls)
        let name = String(cString: namePtr)

        // Filter out obvious non-class names (empty, starts with underscore-underscore for internal)
        guard !name.isEmpty, name != "nil" else { continue }

        ctx.entries.append(HeapEntry(address: addr, size: size, className: name))
        ctx.count += 1
    }
}
