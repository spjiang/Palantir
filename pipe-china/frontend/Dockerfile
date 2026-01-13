# 使用具体 tag，规避镜像元数据异常
FROM node:18.20.4-alpine3.19

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 8081
CMD ["npm", "run", "dev", "--", "--host", "--port", "8081"]
