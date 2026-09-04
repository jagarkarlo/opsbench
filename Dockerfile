FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system --gid 10001 opsbench \
	&& useradd --system --uid 10001 --gid 10001 --no-create-home opsbench \
	&& mkdir -p /app/data \
	&& chown -R opsbench:opsbench /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scenarios ./scenarios
COPY --from=frontend-build /frontend/dist ./frontend-dist

RUN pip install --no-cache-dir -e .

USER 10001:10001

EXPOSE 8080

ENTRYPOINT ["opsbench", "serve", "--host", "0.0.0.0", "--port", "8080", "--gallery-path", "scenarios", "--db", "benchmarks.db", "--frontend-path", "frontend-dist"]
