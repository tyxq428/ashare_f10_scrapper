.PHONY: install test lint serve fetch docker

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

serve:
	ashare-f10 serve --reload

fetch:
	ashare-f10 fetch $(CODE)

docker:
	docker compose up --build
