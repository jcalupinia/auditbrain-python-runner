# Build del Portal de Clientes (frontend-client) para Coolify/Hetzner.
# Contexto = raiz del repo, para incluir frontend-shared (@auditbrain/shared, file:../frontend-shared).
FROM node:20-alpine AS build
WORKDIR /repo
COPY frontend-shared ./frontend-shared
COPY frontend-client ./frontend-client
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
RUN cd frontend-shared && npm ci && cd ../frontend-client && npm ci && npm run build

FROM nginx:alpine
COPY --from=build /repo/frontend-client/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
