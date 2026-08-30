# Dockerfile frontend — Mục Q của Checklist. Checklist chỉ yêu cầu Dockerfile
# riêng cho backend, nhưng docker-compose.yml (Q) cần cả service frontend để
# `docker compose up` chạy được toàn bộ ứng dụng bằng một lệnh — build tĩnh
# rồi phục vụ qua nginx (nhẹ hơn nhiều so với chạy Node server cho SPA thuần).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
