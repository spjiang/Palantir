# 城市暴雨内涝指挥（演示级）- 一键闭环 Demo

本目录是对 `应急安全AI操作系统方案书V7.md` 的**演示级可运行实现**，技术栈：

- 前端：Vue3
- 后端：Python（FastAPI）
- 智能体：LangChain
- 大模型：DeepSeek（可选；无 Key 时自动降级为规则式智能体）
- 小模型：开源（纯 Python 可解释打分，演示级风险评分/解释）
- 部署：docker-compose（含模型服务同样 compose 部署）

## 一键启动

1. 进入目录：

```bash
cd demo-os
```

1. （可选）设置 DeepSeek：

```bash
export DEEPSEEK_API_KEY="你的Key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"  # 如需自定义
export DEEPSEEK_MODEL="deepseek-chat"
```

1. （推荐）设置对外访问地址（给浏览器用；默认 `10.156.196.228`）：

```bash
export PUBLIC_HOST="10.156.196.228"
```

1. 启动（使用新版 Compose v2：`docker compose`，不要用老的 `docker-compose`）：

```bash
docker compose up -d --build
```

## 访问入口

- 前端：`http://<PUBLIC_HOST>:7080`
- 后端 API：`http://<PUBLIC_HOST>:7000/docs`
- 智能体服务：`http://<PUBLIC_HOST>:7001/docs`
- 小模型服务：`http://<PUBLIC_HOST>:7002/docs`

## 常见报错：`KeyError: 'ContainerConfig'`

如果你看到类似：

- `ERROR: for frontend 'ContainerConfig'`
- `KeyError: 'ContainerConfig'`

通常是因为服务器上在用 **老的 `docker-compose`(Python 版 1.x，例如 1.29.2)**，它与新版 Docker Engine（例如 28.x）不兼容。

解决方式：

```bash
# 1) 用 Compose v2（docker 自带插件）
docker compose version

# 2) 清理旧容器/孤儿容器后重建
docker compose down --remove-orphans
docker compose up -d --build
```

## 演示闭环（对应 V7 1.1）

1. 风险热力图/TopN：前端调用后端 `/risk/topn`
1. 智能体研判：前端调用智能体 `/agent/chat`（智能体会调用后端工具）
1. 一键生成任务包并下发：智能体工具 `create_task_pack` + `trigger_workflow`
1. 移动端回执：前端“任务”页回执 `/workflow/tasks/{id}/ack`
1. 一键生成战报：`/reports/incidents/{id}`

## 目录结构

- `docker-compose.yaml`：一键编排
- `services/api/`：后端 API（数据/本体查询/工作流/战报）
- `services/model/`：小模型推理服务（开源）
- `services/agent/`：LangChain 智能体服务（DeepSeek 可选）
- `frontend/`：Vue3 前端
