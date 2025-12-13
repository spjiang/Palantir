FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml /app/pyproject.toml

# 演示级：使用 pip 安装（构建时需要网络；在你的环境中构建即可）
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir .

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


