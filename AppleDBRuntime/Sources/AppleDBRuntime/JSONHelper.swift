import Foundation

enum JSONHelper {
    static func serialize(_ value: Any) -> String {
        guard let data = try? JSONSerialization.data(
            withJSONObject: value,
            options: [.sortedKeys]
        ) else {
            return "[]"
        }
        return String(data: data, encoding: .utf8) ?? "[]"
    }

    static func errorJSON(_ message: String) -> String {
        serialize(["error": message])
    }
}
