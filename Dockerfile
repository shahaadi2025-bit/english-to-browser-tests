# Isolated runner: docker build -t nl-tester . && docker run --rm -e ANTHROPIC_API_KEY nl-tester "your test" --url https://example.com
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install --with-deps chromium
COPY . .
RUN useradd -m runner && chown -R runner /app
USER runner
ENTRYPOINT ["python", "run_test.py"]
