# Developer Notes

## Installation

For development, the recommended approach is to use Docker:

## Running OpenHAB in Docker

A docker-compose file is provided for running both OpenHAB and the MCP server in containers.
Run the following command to start the containers:

```bash
# Using docker-compose directly
docker-compose up -d

# Using Make
make dev-env
```

The OpenAPI spec for OpenHAB is available at: http://localhost:18080/rest/spec

The MCP server will be available at port 8081 and will automatically connect to the OpenHAB instance.

## Development Commands

For development, the following Docker-based commands are available:

```bash
# Build the Docker image
make docker-build

# Run the Docker container
make docker-run

# Stop the Docker container
make docker-stop

# Run both OpenHAB and MCP server using docker-compose
make dev-env
```

The Docker container is configured to use environment variables for connecting to the OpenHAB instance. These can be set in the docker-compose.yml file or passed directly to the docker run command.

## Development Workflow

1. Build the Docker image using `make docker-build`
2. Start the OpenHAB container using `docker-compose up -d` or `make dev-env`
3. Configure your environment variables in the docker-compose.yml file
4. Run the MCP server using `make docker-run`
5. Test your changes

## Cleaning Up

To clean up development artifacts:

```bash
make clean
```
