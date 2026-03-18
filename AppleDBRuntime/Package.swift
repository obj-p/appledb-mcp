// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AppleDBRuntime",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "AppleDBRuntime", type: .dynamic, targets: ["AppleDBRuntime"]),
    ],
    targets: [
        .target(
            name: "AppleDBRuntime",
            path: "Sources/AppleDBRuntime"
        ),
    ]
)
