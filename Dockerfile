FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scenarios ./scenarios

RUN pip install --no-cache-dir -e .

EXPOSE 8080

ENTRYPOINT ["opsbench", "serve", "--host", "0.0.0.0", "--port", "8080", "--gallery-path", "scenarios", "--db", "benchmarks.db"]
