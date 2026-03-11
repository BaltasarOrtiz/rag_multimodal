# ── Stage 1: Build ──────────────────────────────────────────
FROM node:22-alpine3.21 AS builder
RUN apk update && apk upgrade --no-cache
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: Serve con nginx ────────────────────────────────
FROM nginx:1.27-alpine AS final
RUN apk update && apk upgrade --no-cache
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /usr/share/nginx/html \
    && touch /run/nginx.pid \
    && chown nginx:nginx /run/nginx.pid
USER nginx
EXPOSE 80
