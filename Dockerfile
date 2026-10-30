FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY archdiagram ./archdiagram
COPY mcp_server ./mcp_server
COPY tools ./tools

RUN pip install --no-cache-dir ".[mcp]" \
    && useradd --create-home --uid 10001 appuser

USER appuser
EXPOSE 8080
CMD ["python", "-m", "mcp_server.server"]
