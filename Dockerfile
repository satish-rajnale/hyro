FROM python:3.13.3-slim
WORKDIR /app
COPY pyproject.toml ./
COPY hyro ./hyro
COPY frontend ./frontend
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir .
CMD ["uvicorn", "hyro.api:app", "--host", "0.0.0.0", "--port", "8000"]
