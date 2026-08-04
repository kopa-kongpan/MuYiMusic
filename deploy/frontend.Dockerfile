FROM node:22-bookworm-slim AS web-build

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

WORKDIR /workspace

RUN corepack enable && corepack prepare pnpm@11.15.1 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps ./apps
COPY packages ./packages

RUN pnpm install --frozen-lockfile
RUN pnpm build:admin

ARG TARO_APP_API_BASE_URL=""
ENV TARO_APP_API_BASE_URL=$TARO_APP_API_BASE_URL
RUN pnpm --filter @muyimusic/miniapp build:h5

FROM nginx:1.27-alpine AS admin-runtime

COPY deploy/nginx/admin.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /workspace/apps/admin/dist /usr/share/nginx/html

EXPOSE 80

FROM nginx:1.27-alpine AS h5-runtime

COPY deploy/nginx/h5.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /workspace/apps/miniapp/dist/h5 /usr/share/nginx/html

EXPOSE 80
