# Use a Python image with Python 3.12
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables with defaults that can be overridden at runtime
ENV OPENHAB_URL=http://openhab:8080
ENV OPENHAB_API_TOKEN=""
ENV OPENHAB_USERNAME=""
ENV OPENHAB_PASSWORD=""

# Run the MCP server when the container launches
CMD ["python", "openhab_mcp_server.py"]
