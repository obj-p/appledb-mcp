import Foundation
import ObjectiveC

enum ObjectIntrospector {

    /// Describe an object at the given address: class chain, ivars, properties.
    static func describe(address: UInt) -> [String: Any] {
        guard let ptr = UnsafeRawPointer(bitPattern: address) else {
            return ["error": "Invalid address"]
        }

        let obj = unsafeBitCast(ptr, to: AnyObject.self)
        let cls: AnyClass = object_getClass(obj) ?? type(of: obj)

        var result: [String: Any] = [
            "address": String(format: "0x%lx", address),
            "class": String(cString: class_getName(cls)),
            "size": class_getInstanceSize(cls),
            "superclasses": superclassChain(cls),
            "ivars": ivarList(cls),
            "properties": propertyList(cls),
        ]

        // Add instance-specific ivar values
        result["ivarValues"] = ivarValues(obj, cls: cls)

        return result
    }

    /// Get the superclass chain for a class.
    static func superclassChain(_ cls: AnyClass) -> [String] {
        var chain: [String] = []
        var current: AnyClass? = class_getSuperclass(cls)
        while let c = current {
            chain.append(String(cString: class_getName(c)))
            current = class_getSuperclass(c)
        }
        return chain
    }

    /// List ivars declared on a class (not inherited).
    static func ivarList(_ cls: AnyClass) -> [[String: Any]] {
        var count: UInt32 = 0
        guard let ivars = class_copyIvarList(cls, &count) else { return [] }
        defer { free(ivars) }

        var result: [[String: Any]] = []
        for i in 0..<Int(count) {
            let ivar = ivars[i]
            var info: [String: Any] = [:]

            if let name = ivar_getName(ivar) {
                info["name"] = String(cString: name)
            }
            if let encoding = ivar_getTypeEncoding(ivar) {
                info["type"] = String(cString: encoding)
            }
            info["offset"] = ivar_getOffset(ivar)

            result.append(info)
        }
        return result
    }

    /// List properties declared on a class.
    static func propertyList(_ cls: AnyClass) -> [[String: Any]] {
        var count: UInt32 = 0
        guard let props = class_copyPropertyList(cls, &count) else { return [] }
        defer { free(props) }

        var result: [[String: Any]] = []
        for i in 0..<Int(count) {
            let prop = props[i]
            var info: [String: Any] = [
                "name": String(cString: property_getName(prop)),
            ]
            if let attrs = property_getAttributes(prop) {
                info["attributes"] = String(cString: attrs)
            }
            result.append(info)
        }
        return result
    }

    /// Read ivar values from a live object. Only reads object-type ivars safely.
    static func ivarValues(_ obj: AnyObject, cls: AnyClass) -> [[String: Any]] {
        var count: UInt32 = 0
        guard let ivars = class_copyIvarList(cls, &count) else { return [] }
        defer { free(ivars) }

        var result: [[String: Any]] = []
        for i in 0..<Int(count) {
            let ivar = ivars[i]
            guard let name = ivar_getName(ivar) else { continue }
            let nameStr = String(cString: name)
            let offset = ivar_getOffset(ivar)

            guard let encoding = ivar_getTypeEncoding(ivar) else {
                result.append(["name": nameStr, "value": "<unknown type>"])
                continue
            }
            let typeStr = String(cString: encoding)

            if typeStr.hasPrefix("@") {
                // Object type — safe to read via object_getIvar
                if let value = object_getIvar(obj, ivar) {
                    let refObj = value as AnyObject
                    let refClass = String(cString: class_getName(object_getClass(refObj)!))
                    let refAddr = unsafeBitCast(refObj, to: UInt.self)
                    result.append([
                        "name": nameStr,
                        "type": typeStr,
                        "class": refClass,
                        "address": String(format: "0x%lx", refAddr),
                    ])
                } else {
                    result.append(["name": nameStr, "type": typeStr, "value": "nil"])
                }
            } else {
                // Primitive type — read raw bytes based on encoding
                let basePtr = unsafeBitCast(obj, to: UnsafeRawPointer.self)
                let valueStr = readPrimitiveValue(basePtr + offset, encoding: typeStr)
                result.append(["name": nameStr, "type": typeStr, "value": valueStr])
            }
        }
        return result
    }

    /// Get outbound object references from an object (ivars that are object pointers).
    static func outboundReferences(address: UInt) -> [[String: Any]] {
        guard let ptr = UnsafeRawPointer(bitPattern: address) else { return [] }
        let obj = unsafeBitCast(ptr, to: AnyObject.self)
        let cls: AnyClass = object_getClass(obj) ?? type(of: obj)

        var refs: [[String: Any]] = []
        var currentClass: AnyClass? = cls

        // Walk the class hierarchy to get all ivars (including inherited)
        while let c = currentClass {
            var count: UInt32 = 0
            if let ivars = class_copyIvarList(c, &count) {
                defer { free(ivars) }
                for i in 0..<Int(count) {
                    let ivar = ivars[i]
                    guard let encoding = ivar_getTypeEncoding(ivar),
                          String(cString: encoding).hasPrefix("@") else { continue }

                    guard let value = object_getIvar(obj, ivar) else { continue }
                    let refObj = value as AnyObject
                    let refAddr = unsafeBitCast(refObj, to: UInt.self)
                    guard refAddr != 0 else { continue }

                    let refClass = String(cString: class_getName(object_getClass(refObj)!))
                    let ivarName = ivar_getName(ivar).map { String(cString: $0) } ?? "<unnamed>"

                    refs.append([
                        "ivar": ivarName,
                        "address": String(format: "0x%lx", refAddr),
                        "class": refClass,
                    ])
                }
            }
            currentClass = class_getSuperclass(c)
        }

        return refs
    }

    /// Read a primitive value from memory based on ObjC type encoding.
    private static func readPrimitiveValue(_ ptr: UnsafeRawPointer, encoding: String) -> String {
        switch encoding {
        case "i": return "\(ptr.load(as: Int32.self))"
        case "I": return "\(ptr.load(as: UInt32.self))"
        case "q": return "\(ptr.load(as: Int64.self))"
        case "Q": return "\(ptr.load(as: UInt64.self))"
        case "s": return "\(ptr.load(as: Int16.self))"
        case "S": return "\(ptr.load(as: UInt16.self))"
        case "c", "B": return "\(ptr.load(as: Int8.self))"
        case "C": return "\(ptr.load(as: UInt8.self))"
        case "f": return "\(ptr.load(as: Float.self))"
        case "d": return "\(ptr.load(as: Double.self))"
        case "l": return "\(ptr.load(as: Int32.self))"
        case "L": return "\(ptr.load(as: UInt32.self))"
        default: return "<\(encoding)>"
        }
    }
}
