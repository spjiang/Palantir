# 使用具体 tag，规避镜像元数据异常
FROM node:18.20.4-alpine3.19

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json package-lock.json* ./
RUN npm config set registry ${NPM_REGISTRY} && npm install

COPY . .

EXPOSE 8081
CMD ["npm", "run", "dev", "--", "--host", "--port", "8081"]
