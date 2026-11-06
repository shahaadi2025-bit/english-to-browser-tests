# Isolated runner: docker build -t nl-tester . ; docker run --rm -e OLLAMA_HOST=http://host.docker.internal:11434 nl-tester "your test" --url https://example.com
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install --with-deps chromium
COPY . .
RUN useradd -m runner && chown -R runner /app
USER runner
ENTRYPOINT ["python", "run_test.py"]
