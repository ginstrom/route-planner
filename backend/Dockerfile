FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml ./
COPY backend ./backend

RUN uv venv /app/.venv \
  && uv pip install --python /app/.venv/bin/python /app

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
