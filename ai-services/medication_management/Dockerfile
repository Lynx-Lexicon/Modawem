FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

# ---

FROM base AS test

RUN python -m pip install --no-cache-dir ".[dev]"

COPY tests ./tests
RUN pytest -q

# ---

FROM base AS runtime

RUN python -m pip install --no-cache-dir .

ENV MEDICATION_MANAGEMENT_SERVICE_HOST=0.0.0.0
ENV MEDICATION_MANAGEMENT_SERVICE_PORT=8080
EXPOSE 8080

CMD ["medication-management-server"]
