# 可配置基础镜像；默认使用官方镜像，必要时可覆盖为内网/镜像源
ARG NODE_IMAGE=docker.io/library/node:18.20.4-alpine3.19
FROM ${NODE_IMAGE}

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm config set registry ${NPM_REGISTRY} && npm install

COPY . .

EXPOSE 8081
CMD ["npm", "run", "dev", "--", "--host", "--port", "8081"]
