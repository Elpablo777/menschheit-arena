FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

# Nicht-root
RUN useradd --create-home --uid 10001 apparen \
    && mkdir -p /app/data /app/reports \
    && chown -R apparen:apparen /app
USER apparen

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite:////app/data/menschheit.db \
    LLM_PROVIDER=mock \
    PENTEST_EXECUTION_ENABLED=false \
    ALLOW_PUBLIC_TARGETS=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status == 200 else 1)"

CMD ["menschheit", "serve"]