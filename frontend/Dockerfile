FROM node:24.18.0-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24.18.0-alpine AS builder
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24.18.0-alpine AS runtime
ENV NODE_ENV=production
WORKDIR /app
RUN addgroup --system --gid 10001 build360 \
    && adduser --system --uid 10001 --ingroup build360 build360
COPY --from=builder --chown=build360:build360 /app/.next/standalone ./
COPY --from=builder --chown=build360:build360 /app/.next/static ./.next/static
COPY --from=builder --chown=build360:build360 /app/public ./public
USER build360
EXPOSE 3000
CMD ["node", "server.js"]

