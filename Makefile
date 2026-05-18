.PHONY: run install

run:
	uv run python main.py

install:
	uv sync --dev
