.PHONY: build-runtime clean-runtime test install

build-runtime:
	cd AppleDBRuntime && bash build.sh

clean-runtime:
	rm -rf frameworks/AppleDBRuntime.framework
	rm -rf AppleDBRuntime/.build

test:
	uv run pytest tests/ -v --ignore=tests/lldb_service

install:
	pip install -e ".[dev]"
