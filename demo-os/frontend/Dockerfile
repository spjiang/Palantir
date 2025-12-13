FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json

# 演示级：构建时需要网络安装依赖（在你的环境中构建即可）
RUN npm install

COPY index.html vite.config.ts /app/
COPY src /app/src

EXPOSE 8080

CMD ["npm", "run", "dev"]


