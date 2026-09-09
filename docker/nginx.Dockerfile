# 拾贝 nginx 反代镜像：配置内嵌（避免依赖运行时 bind 挂载）。
# 前缀参数化：NGINX_PREFIX 决定对外子路径（如 /shibei/ 或 /apps/shibei/），
# 构建时把内嵌配置里的 /shibei 统一替换为目标前缀。
FROM nginx:1.27-alpine
ARG NGINX_PREFIX=/shibei/
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN P="$(printf '%s' "$NGINX_PREFIX" | sed 's|/$||')" \
    && case "$P" in /shibei) ;; *) sed -i "s|/shibei|$P|g" /etc/nginx/conf.d/default.conf ;; esac
