# 可配置基础镜像，避免 Docker daemon 的 docker.io 镜像源/代理不可达导致构建失败
ARG NODE_IMAGE=registry.cn-hangzhou.aliyuncs.com/library/node:18.20.4-alpine3.19
FROM ${NODE_IMAGE}

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm config set registry ${NPM_REGISTRY} && npm install

COPY . .

EXPOSE 8081
CMD ["npm", "run", "dev", "--", "--host", "--port", "8081"]
