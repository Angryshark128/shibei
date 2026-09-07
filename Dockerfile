# ---------- 前端构建（node） ----------
FROM node:22-alpine AS frontend-build
WORKDIR /build
# 先装依赖再拷源码，利用层缓存
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
ARG VITE_BASE=/shibei/
ENV VITE_BASE=${VITE_BASE}
RUN npm run build

# ---------- 运行时（python） ----------
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    SHIBEI_PORT=8000 \
    SHIBEI_BASE_PATH=/shibei/
COPY web/ /app/web/
COPY analyzer.py crawler.py models.py config.json ./
COPY sources/ /app/sources/
COPY --from=frontend-build /build/dist/ /app/static/
RUN pip install --no-cache-dir flask waitress
EXPOSE 8000
CMD ["python", "-m", "web.app"]
