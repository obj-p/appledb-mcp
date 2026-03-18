#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRAMEWORK_DIR="$PROJECT_ROOT/frameworks"
FRAMEWORK_NAME="AppleDBRuntime"

echo "Building $FRAMEWORK_NAME..."

# Build using SwiftPM
cd "$SCRIPT_DIR"
swift build -c release 2>&1

# Locate the built dylib
BUILD_DIR="$SCRIPT_DIR/.build/release"
DYLIB="$BUILD_DIR/lib${FRAMEWORK_NAME}.dylib"

if [ ! -f "$DYLIB" ]; then
    echo "ERROR: Built library not found at $DYLIB"
    exit 1
fi

# Create framework bundle structure
FRAMEWORK_BUNDLE="$FRAMEWORK_DIR/$FRAMEWORK_NAME.framework"
rm -rf "$FRAMEWORK_BUNDLE"
mkdir -p "$FRAMEWORK_BUNDLE"

# Copy binary
cp "$DYLIB" "$FRAMEWORK_BUNDLE/$FRAMEWORK_NAME"

# Fix install name
install_name_tool -id "@rpath/$FRAMEWORK_NAME.framework/$FRAMEWORK_NAME" \
    "$FRAMEWORK_BUNDLE/$FRAMEWORK_NAME"

# Copy Swift module files for LLDB symbol resolution
SWIFTMODULE_SRC="$BUILD_DIR"
if [ -d "$SWIFTMODULE_SRC/${FRAMEWORK_NAME}.swiftmodule" ]; then
    mkdir -p "$FRAMEWORK_BUNDLE/Modules/$FRAMEWORK_NAME.swiftmodule"
    cp "$SWIFTMODULE_SRC/$FRAMEWORK_NAME.swiftmodule"/* \
        "$FRAMEWORK_BUNDLE/Modules/$FRAMEWORK_NAME.swiftmodule/" 2>/dev/null || true
fi

# Create Info.plist
cat > "$FRAMEWORK_BUNDLE/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.appledb.runtime</string>
    <key>CFBundleName</key>
    <string>AppleDBRuntime</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>AppleDBRuntime</string>
    <key>CFBundlePackageType</key>
    <string>FMWK</string>
</dict>
</plist>
PLIST

# Ad-hoc code sign
codesign --force --sign - "$FRAMEWORK_BUNDLE/$FRAMEWORK_NAME"

echo ""
echo "Built: $FRAMEWORK_BUNDLE"
echo "Ready for: load_framework('AppleDBRuntime')"
