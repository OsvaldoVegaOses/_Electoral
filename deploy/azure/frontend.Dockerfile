FROM node:22.16.0-bookworm-slim AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# Containers within this Container App share a network namespace.
RUN sed -i 's|http://backend:8000|http://127.0.0.1:8000|; s|X-Forwarded-Proto $scheme|X-Forwarded-Proto $http_x_forwarded_proto|' /etc/nginx/conf.d/default.conf
EXPOSE 80
