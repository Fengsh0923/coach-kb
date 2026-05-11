FROM caddy:2-builder-alpine AS builder
ENV GOPROXY=https://goproxy.cn,direct
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:2-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
