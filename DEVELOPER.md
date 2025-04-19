# Developer Notes

## Installation

For development, you can use the provided installation script or Makefile:

```bash
# Using the installation script
python install.py

# Using Make
make install
```

## Running OpenHAB in Docker

A docker-compose file is provided for running OpenHAB in a container to test the API.
Run the following command to start the container:

```bash
# Using docker-compose directly
docker-compose up

# Using Make
make dev-env
```

The OpenAPI spec for OpenHAB is available at: http://localhost:18080/rest/spec

## Development Workflow

1. Install dependencies using the installation script or Makefile
2. Start the OpenHAB container using docker-compose
3. Configure your .env file with the appropriate connection details
4. Run the MCP server using `make run` or `uv run openhab_mcp_server.py`
5. Test your changes

## Cleaning Up

To clean up development artifacts:

```bash
make clean
```
