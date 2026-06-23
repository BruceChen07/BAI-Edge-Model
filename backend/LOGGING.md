# 后端日志架构说明

## 1. 目标
- 为后端提供结构化、可持久化、可筛选的日志体系。
- 覆盖接口请求响应、核心业务流程、第三方服务调用、异常抛出全链路。
- 支持通过 `trace_id` 串联单次请求，快速定位 `Ollama` 超时等问题。

## 2. 日志输出位置
- 主日志文件：`storage/logs/app.log`
- 错误日志文件：`storage/logs/error.log`
- 输出格式：单行 JSON

## 3. 日志字段规范
- `timestamp`：日志时间，ISO 风格字符串
- `level`：`debug` / `info` / `warning` / `error`
- `logger`：Python logger 名称
- `module`：业务模块，例如 `api`、`chat`、`ollama`、`ingest`
- `event`：稳定事件名，例如 `ollama.chat.failed`
- `message`：人类可读说明
- `trace_id`：请求链路 ID，可用于检索
- `context`：结构化上下文字段
- `exception`：错误级别日志的完整堆栈

## 4. 日志分级
- `debug`：细粒度调试信息，默认不建议在生产长期开启
- `info`：请求开始/结束、业务成功、第三方调用成功
- `warning`：可恢复异常、配置风险、超时前兆、降级场景
- `error`：接口失败、第三方服务失败、未处理异常

## 5. Trace ID 规则
- HTTP 中间件会为每个请求生成 `trace_id`
- 客户端可通过 `X-Trace-Id` 传入自定义链路 ID
- 服务端响应头会返回 `X-Trace-Id`
- 聊天接口、日志查询、第三方调用日志都会写入相同 `trace_id`
- `session_id` 作为业务上下文保存在 `context.session_id`，不替代请求链路 ID

## 6. Ollama 专属日志
- 事件：
  - `ollama.list_models.succeeded`
  - `ollama.list_models.failed`
  - `ollama.chat.request`
  - `ollama.chat.response`
  - `ollama.chat.failed`
- 关键上下文字段：
  - `base_url`
  - `model_name`
  - `timeout_seconds`
  - `message_count`
  - `request_payload`
  - `status_code`
  - `elapsed_ms`
  - `exception`

## 7. 配置项
- `LOG_LEVEL`
- `LOG_MAX_BYTES`
- `LOG_BACKUP_COUNT`
- `OLLAMA_LIST_TIMEOUT_SECONDS`
- `OLLAMA_CONNECT_TIMEOUT_SECONDS`
- `OLLAMA_READ_TIMEOUT_SECONDS`
- `OLLAMA_WRITE_TIMEOUT_SECONDS`
- `OLLAMA_POOL_TIMEOUT_SECONDS`

## 8. 日志轮转
- 使用 `RotatingFileHandler`
- 默认单文件上限：`5 MB`
- 默认保留备份数：`5`
- 超出上限时自动轮转，避免磁盘无限增长

## 9. 日志检索
- 查询接口：`GET /api/v1/logs`
- 支持筛选参数：
  - `level`
  - `module`
  - `trace_id`
  - `start_time`
  - `end_time`
  - `limit`

## 10. Ollama 超时排查流程
1. 调用 `GET /api/v1/logs?module=ollama&limit=100`
2. 查看是否存在 `ollama.chat.failed`
3. 关注以下字段：
   - `model_name`
   - `timeout_seconds`
   - `elapsed_ms`
   - `request_payload`
   - `exception`
4. 若 `elapsed_ms` 接近 `read timeout`，优先判断为模型响应慢或机器负载高
5. 用 `ollama ps` 检查当前模型是否在 CPU 高负载运行
6. 如为大模型 CPU 推理场景，优先增大 `OLLAMA_READ_TIMEOUT_SECONDS`

## 11. 本次问题结论
- `Ollama` 服务本身可访问，不是网络断连问题
- 根因是大模型在当前机器上的响应时间超过原先固定 `120s` 读超时阈值
- 通过引入可配置超时和结构化日志后，问题已可复现、可定位、可验证
