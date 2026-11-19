# 性能基准

基准脚本位于 [`scripts/benchmark.py`](../scripts/benchmark.py)，覆盖模型校验、消息转换、SQLite、API 分发、HTTP 和 WebSocket。

测试环境为 i5-1135G7 / 16GB / Linux，Python 3.11，默认 4 个 API worker：

```shell
uv run python scripts/benchmark.py --rtt-ms 20
```

`--rtt-ms 20` 会为每次模拟 QQ 协议交互增加 20 ms RTT。HTTP 和 WebSocket 使用本机回环，QQ 登录和服务器响应由 Stub 替代。结果适合比较版本变化，不代表线上 QQ 的固定吞吐。

## 协议与端到端

| 场景 | 吞吐 | 延迟 |
|------|------|------|
| 队列分发 `send_group_msg`，8 个在途请求 | ~95 req/s | p50 84.0 ms |
| HTTP 串行 `send_group_msg` | ~21 req/s | p50 47.0 ms |
| HTTP `send_group_msg`，8 连接并发 | ~93 req/s | p50 84.4 ms |
| 正向 WebSocket `send_group_msg`，500 请求流水线 | ~92 req/s | p50 2.76 s |
| WebSocket 事件推送 | ~8,200 条/s | 500 条约 60.7 ms |

群消息发送包含“发送消息”和“反查 `rand`”两次模拟 QQ RTT。WebSocket 流水线的 p50 包含 500 个已排队请求的等待时间，不是单次请求的网络 RTT。

## API Worker 扩展性

固定 32 个在途请求，每次 QQ 交互模拟 20 ms RTT：

| `api_workers` | 群消息 | 私聊消息 |
|---------------|--------|----------|
| 1 | ~24 req/s | ~47 req/s |
| 2 | ~48 req/s | ~93 req/s |
| 4 | ~94 req/s | ~183 req/s |
| 8 | ~184 req/s | ~356 req/s |
| 16 | ~351 req/s | ~643 req/s |

群消息需要两次模拟 RTT，私聊只需要一次。默认值 `4` 是保守配置；提高 worker 数可以提升吞吐，但还需要考虑 QQ 服务端限流、数据库压力和实际并发量。

## CPU 与存储

| 场景 | 吞吐 | p50 |
|------|------|-----|
| API 请求 JSON 校验 | ~20,100 req/s | 48.2 µs |
| 事件序列化 | ~287,000 req/s | 3.1 µs |
| 消息段列表校验 | ~154,600 req/s | 6.2 µs |
| `to_onebot_msg` 纯文本链 | ~253,800 req/s | 3.8 µs |
| `to_onebot_msg` 混合链 | ~53,200 req/s | 17.8 µs |
| SQLite 消息写入 | ~11,500 req/s | 72.9 µs |
| SQLite 消息主键读取 | ~12,200 req/s | 68.7 µs |
| UID→UIN 缓存读取 | ~1,884,900 req/s | 0.4 µs |

完整基准平均 RSS 约 76.9 MB，峰值约 83.1 MB，数据库约 1.4 MB。

真实 QQ 网络、协议服务器限流和账号所在地区都会明显影响端到端结果。
