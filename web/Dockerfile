FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Static assets only; the site config is mounted from nginx/nginx.conf by docker-compose.
FROM nginx:1.27-alpine
COPY --from=build /web/dist /usr/share/nginx/html
