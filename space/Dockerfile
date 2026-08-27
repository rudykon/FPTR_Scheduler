FROM gcc:14-bookworm AS builder

WORKDIR /build
COPY src/ ./src/
RUN g++ -std=c++17 -O2 src/scheduler.cpp src/core.cpp -o scheduler

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    PORT=7860

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
COPY --from=builder /build/scheduler /app/scheduler

RUN useradd --create-home --uid 1000 user \
    && chown -R user:user /app \
    && chmod 755 /app/scheduler

USER user
EXPOSE 7860

CMD ["python", "app.py"]
