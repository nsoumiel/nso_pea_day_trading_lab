FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TZ=Europe/Paris
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir '.[yahoo]'
COPY config.toml ./config.toml
ENTRYPOINT ["python", "-m", "pea_day_trading_lab"]
CMD ["status"]
