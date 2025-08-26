.PHONY: dev-env clean docker-build docker-run docker-stop

docker-build:
	podman build -t openhab-mcp .

docker-run:
	podman run -d --rm -p 8081:8080 \
		-e OPENHAB_URL=${OPENHAB_URL} \
		-e OPENHAB_API_TOKEN=${OPENHAB_API_TOKEN} \
		-e OPENHAB_USERNAME=${OPENHAB_USERNAME} \
		-e OPENHAB_PASSWORD=${OPENHAB_PASSWORD} \
		-e TRANSPORT_TYPE=${TRANSPORT_TYPE} \
		--name openhab-mcp \
		openhab-mcp

docker-stop:
	podman stop openhab-mcp || true

dev-env:
	podman-compose up -d

clean:
	rm -rf __pycache__
	rm -rf *.egg-info
