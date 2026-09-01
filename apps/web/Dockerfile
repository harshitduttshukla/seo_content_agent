FROM node:20-alpine AS builder

WORKDIR /app
COPY packages/shared-types ./packages/shared-types
COPY apps/web/package*.json ./apps/web/
WORKDIR /app/apps/web
RUN npm ci

COPY apps/web ./
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app/apps/web

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /app/packages/shared-types /app/packages/shared-types
COPY --from=builder /app/apps/web/package*.json ./
COPY --from=builder /app/apps/web/node_modules ./node_modules
COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public

EXPOSE 3000

CMD ["npm", "run", "start"]
