FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Etapa de pruebas: docker build --target pruebas -t <imagen>:pruebas . && docker run --rm <imagen>:pruebas
FROM base AS pruebas
RUN pip install --no-cache-dir pytest==8.3.4 fakeredis==2.26.2
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q", "tests"]

FROM base AS final
RUN useradd --uid 10001 --no-create-home aulanube
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
