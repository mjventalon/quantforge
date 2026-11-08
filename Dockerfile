# quantforge web app — production image
# Build:  docker build -t quantforge .
# Run:    docker run -p 8501:8501 -e QUANTFORGE_CERT_SECRET=... quantforge
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QUANTFORGE_ALLOW_CODE_EXECUTION=0 \
    XDG_CACHE_HOME=/home/app/.cache \
    QUANTFORGE_DATA_DIR=/data

# g++ builds the C++ pricing engine during the image build
RUN apt-get update && apt-get install -y --no-install-recommends g++ curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home app && mkdir -p /data && chown app /data
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY .streamlit ./.streamlit
RUN pip install ".[app,stats]"

USER app
RUN python -m quantforge.native >/dev/null && echo "C++ engine built"

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8501/_stcore/health || exit 1
CMD ["sh", "-c", "streamlit run $(python -c 'import quantforge.app, pathlib; print(pathlib.Path(quantforge.app.__file__).parent / \"app.py\")') --server.port=${PORT:-8501} --server.address=0.0.0.0"]
