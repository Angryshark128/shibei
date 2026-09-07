# 拾贝 nginx 反代镜像：配置内嵌（避免依赖运行时 bind 挂载）
FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
