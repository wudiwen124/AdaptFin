FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -e ".[server,data]"

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "advisor.service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
