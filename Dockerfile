# 只容器化【控制台本体】。7 个微服务是各自独立的仓库，不打包进来 ——
# 它们的在线状态由控制台通过 TCP 探测感知（容器内可用 extra_hosts 指向宿主机）。
FROM python:3.11-slim

LABEL org.opencontainers.image.title="OmniAgent Platform Console"
LABEL org.opencontainers.image.description="企业级全域 AI 智能体控制中枢（控制台 + 编排层）"
LABEL org.opencontainers.image.source="https://github.com/<你的用户名>/OmniAgent-Platform"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OMNI_PORT=8888 \
    OMNI_HOST=0.0.0.0 \
    OMNI_PROBE_HOST=host.docker.internal

WORKDIR /app

# 依赖先行：改代码不会让这一层缓存失效
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py services.yaml ./
COPY templates/ ./templates/
COPY static/ ./static/

# 历史库落盘目录（probes / events 两张表），挂卷用
RUN mkdir -p /app/data

# 非 root 运行
RUN useradd --create-home --shell /bin/bash omni \
    && chown -R omni:omni /app
USER omni

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%d/healthz' % int(__import__('os').environ.get('OMNI_PORT','8888')), timeout=4).status==200 else 1)"

CMD ["sh", "-c", "python server.py"]
