#!/bin/bash
# Cleanup script for appledb-mcp external dependencies

set -e

echo "=== appledb-mcp Cleanup ==="
echo
echo "This will remove external dependencies installed during development."
echo

# Ask for confirmation
read -p "Remove Homebrew Python 3.11 and 3.12? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing Homebrew Python installations..."
    brew uninstall python@3.11 python@3.12 || echo "Some packages may already be removed"
fi

echo

# System Python packages
read -p "Remove system Python user packages (pydantic)? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing system Python user packages..."
    /usr/bin/python3 -m pip uninstall -y pydantic pydantic-settings pydantic_core || echo "Already removed"
fi

echo

# Claude config directory (only if empty)
if [ -d "$HOME/Library/Application Support/Claude" ]; then
    if [ -z "$(ls -A "$HOME/Library/Application Support/Claude")" ]; then
        read -p "Remove empty Claude config directory? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rmdir "$HOME/Library/Application Support/Claude"
            echo "Removed empty Claude config directory"
        fi
    else
        echo "Note: Claude config directory not empty, skipping..."
    fi
fi

echo
echo "✓ Cleanup complete!"
echo
echo "To remove the project repository:"
echo "  cd /Users/obj-p/Projects && rm -rf appledb-mcp"
