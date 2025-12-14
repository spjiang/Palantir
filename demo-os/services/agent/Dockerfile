FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml /app/pyproject.toml

# 远程服务器构建时常见：DNS/出网/证书/镜像源导致 pip “from versions: none”
# 这里：
# - 安装 ca-certificates 保障 HTTPS
# - 从 pyproject.toml 生成临时 requirements.txt，仅安装依赖（避免 `pip install .` 需要打包项目）
# - 安装失败时自动回退到清华镜像重试
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/* && \
    python -c "import tomllib; from pathlib import Path; p=tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8')); deps=p.get('project',{}).get('dependencies',[]); Path('/tmp/requirements.txt').write_text('\\n'.join(deps)+'\\n',encoding='utf-8'); print('Wrote /tmp/requirements.txt with', len(deps), 'deps')" && \
    pip install --no-cache-dir -U pip setuptools wheel && \
    (pip install --no-cache-dir -r /tmp/requirements.txt || \
     pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r /tmp/requirements.txt)

COPY app /app/app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]


