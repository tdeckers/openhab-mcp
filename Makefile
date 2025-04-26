.PHONY: dev-env clean docker-build docker-run docker-stop

docker-build:
	docker build -t openhab-mcp .

docker-run:
	docker run -d --rm -p 8081:8080 \
		-e OPENHAB_URL=${OPENHAB_URL} \
		-e OPENHAB_API_TOKEN=${OPENHAB_API_TOKEN} \
		-e OPENHAB_USERNAME=${OPENHAB_USERNAME} \
		-e OPENHAB_PASSWORD=${OPENHAB_PASSWORD} \
		--name openhab-mcp \
		openhab-mcp

docker-stop:
	docker stop openhab-mcp || true

dev-env:
	docker-compose up -d

clean:
	rm -rf __pycache__
	rm -rf *.egg-info
