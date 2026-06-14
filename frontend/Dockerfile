FROM node:22-alpine AS build

WORKDIR /app

COPY react/package*.json ./

RUN npm install --legacy-peer-deps

COPY react/ .

# Set API URL for Docker environment (nginx will proxy /api to backend)
ENV VITE_API_URL=/api

RUN npm run build


FROM nginx:stable-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

CMD ["/bin/sh", "-c", "envsubst '$API_UPSTREAM_URL' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]