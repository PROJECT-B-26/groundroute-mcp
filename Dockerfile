# GroundRoute MCP server (stdio). Builds a self-contained image that starts the
# server and responds to MCP introspection with no credentials required.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# stdio transport — the client communicates over stdin/stdout.
CMD ["python", "server.py"]
