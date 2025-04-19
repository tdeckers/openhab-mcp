.PHONY: install run dev-env clean

install:
	python install.py

run:
	uv run openhab_mcp_server.py

dev-env:
	docker-compose up -d

clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf *.egg-info
