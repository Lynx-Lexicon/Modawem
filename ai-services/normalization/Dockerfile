FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md rxnorm_normalize.py ./
COPY rxnorm_service ./rxnorm_service

RUN pip install --no-cache-dir .

# Containers need an explicit interface override; do not expose this port
# publicly without private-network isolation or an authenticated gateway.
ENV RXNORM_SERVICE_HOST=0.0.0.0
ENV RXNORM_SERVICE_PORT=8080
EXPOSE 8080

CMD ["rxnorm-server"]
