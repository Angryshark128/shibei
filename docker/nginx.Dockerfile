# 拾贝 nginx 反代镜像：配置内嵌（避免依赖运行时 bind 挂载）。
# 前缀参数化：NGINX_PREFIX 决定对外子路径（如 /shibei/ 或 /apps/shibei/），
# 构建时选择模板：根路径（/）用 nginx-root.conf 直通；子路径用 nginx.conf 并把 /shibei 替换为目标前缀。
FROM nginx:1.27-alpine
ARG NGINX_PREFIX=/shibei/
COPY deploy/ /deploy/
RUN P="$(printf '%s' "$NGINX_PREFIX" | sed 's|/$||')" \
    && if [ -z "$P" ]; then \
         cp /deploy/nginx-root.conf /etc/nginx/conf.d/default.conf; \
       else \
         cp /deploy/nginx.conf /etc/nginx/conf.d/default.conf \
         && case "$P" in /shibei) ;; *) sed -i "s|/shibei|$P|g" /etc/nginx/conf.d/default.conf ;; esac; \
       fi \
    && rm -rf /deploy
