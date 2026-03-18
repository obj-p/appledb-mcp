import Foundation
import ObjectiveC

/// Public API for heap introspection.
/// All methods are @objc static and return JSON strings for LLDB expression eval.
///
/// Usage from LLDB:
///   (lldb) po [AppleDBRuntime heapSummary]
///   (lldb) po [AppleDBRuntime instancesOf:@"UIView"]
///   (lldb) po [AppleDBRuntime describeAddress:0x600001234]
@objc public class AppleDBRuntime: NSObject {

    /// Heap class histogram: count and total size per class.
    /// Returns JSON array sorted by totalSize descending, capped at top 100 classes.
    @objc public static func heapSummary() -> String {
        let entries = HeapWalker.walkHeap()

        // Aggregate by class name
        var classCounts: [String: Int] = [:]
        var classSizes: [String: UInt] = [:]
        for entry in entries {
            classCounts[entry.className, default: 0] += 1
            classSizes[entry.className, default: 0] += entry.size
        }

        // Sort by total size descending
        let sorted = classSizes.sorted { $0.value > $1.value }
        let capped = sorted.prefix(100)

        let result: [[String: Any]] = capped.map { (className, totalSize) in
            [
                "class": className,
                "count": classCounts[className] ?? 0,
                "totalSize": totalSize,
            ]
        }

        return JSONHelper.serialize(result)
    }

    /// Find all instances of a specific class on the heap.
    /// Returns JSON array capped at 1000 instances.
    @objc public static func instances(of className: String) -> String {
        let entries = HeapWalker.walkHeap(classFilter: className, maxResults: 1000)

        let result: [[String: Any]] = entries.map { entry in
            [
                "address": String(format: "0x%lx", entry.address),
                "size": entry.size,
                "class": entry.className,
            ]
        }

        return JSONHelper.serialize(result)
    }

    /// Describe an object at the given memory address.
    /// Returns JSON with class, superclasses, ivars, properties, and ivar values.
    @objc public static func describe(address: UInt) -> String {
        let info = ObjectIntrospector.describe(address: address)
        return JSONHelper.serialize(info)
    }

    /// Get outbound object references from an object.
    /// Returns JSON array of referenced objects with ivar name, address, and class.
    @objc public static func references(from address: UInt) -> String {
        let refs = ObjectIntrospector.outboundReferences(address: address)
        return JSONHelper.serialize(refs)
    }

    /// Detect retain cycles starting from an object.
    /// Returns JSON array of cycle paths.
    @objc public static func retainCycles(from address: UInt, maxDepth: Int) -> String {
        let depth = maxDepth > 0 ? maxDepth : 10
        let cycles = CycleDetector.detect(from: address, maxDepth: depth)

        let result: [[String: Any]] = cycles.map { cycle in
            ["cycle": cycle.nodes]
        }

        return JSONHelper.serialize(result)
    }
}
