# 配置

Euler OneBot 首次启动时会生成 `appconfig.json`。修改后需要重启进程。

仓库中的 `appconfig.schema.json` 由 `BotConfig` 自动生成。保留配置文件开头的 `$schema` 字段后，编辑器可以提供补全和校验。模型变更后可运行：

```shell
uv run python scripts/gen_schema.py
```

## 完整示例

下面的示例展示了所有连接类型。实际使用时只保留需要的连接；`connections` 也可以同时配置多条。

```json
{
  "$schema": "./appconfig.schema.json",
  "log_level": "INFO",
  "log_nf": true,
  "access_token": "",
  "api_workers": 4,
  "event_compatibility": {
    "reaction_event_type": "reaction"
  },
  "connections": [
    {
      "type": "HTTP",
      "url": "http://127.0.0.1:3000"
    },
    {
      "type": "HTTPPost",
      "url": "http://127.0.0.1:8080/onebot",
      "timeout": 5,
      "secret": ""
    },
    {
      "type": "ForwardWebSocket",
      "url": "ws://127.0.0.1:5004"
    },
    {
      "type": "ReverseWebSocket",
      "url": "ws://127.0.0.1:8080",
      "api_url": "",
      "event_url": "",
      "use_universal_client": false,
      "reconnect_interval": 3000
    }
  ],
  "login": {
    "uin": 0,
    "password": "",
    "protocol": "linux",
    "fetch_appinfo": false,
    "signer_url": "https://sign.lagrangecore.org",
    "signer_token": "",
    "use_custom": false,
    "appinfo_path": "./appinfo.json",
    "use_custom_sign_provider": false,
    "sign_provider_path": "./sign_provider.py",
    "sign_provider_entry": "sign_provider",
    "setup_watchdog": false,
    "use_ipv6": false,
    "use_optimum": true
  },
  "heartbeat": {
    "enabled": true,
    "interval": 15000
  }
}
```

## 基础字段

| 字段 | 说明 |
|------|------|
| `$schema` | 编辑器使用的 schema 路径，程序解析时忽略 |
| `log_level` | `TRACE` / `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`，请注意 `DEBUG`的语义差异 |
| `log_nf` | 控制台日志是否使用 Nerd Font 图标 |
| `access_token` | HTTP、正向 WebSocket、反向 WebSocket 的鉴权 Token；留空表示不鉴权 |
| `api_workers` | API 分发 worker 数，默认 `4`，必须大于等于 `1` |
| `connections` | 通信连接列表 |
| `event_compatibility` | 事件字段兼容选项 |
| `login` | QQ 登录参数 |
| `heartbeat` | OneBot 心跳配置 |

`api_workers` 主要影响并发 API 请求。Worker 数、模拟 RTT 与吞吐的关系见 [性能基准](benchmark.md)。

## 登录

QQ 登录、协议参数、签名服务和自定义 sign provider 的说明见 [登录与签名](login.md)。

## 事件兼容

`event_compatibility.reaction_event_type` 默认是 `reaction`。设置为 `group_msg_emoji_like` 后，群表情回应事件的 `notice_type` 会使用该兼容名称，其余字段不变。

```json
{
  "event_compatibility": {
    "reaction_event_type": "group_msg_emoji_like"
  }
}
```

## 心跳

```json
{
  "heartbeat": {
    "enabled": true,
    "interval": 15000
  }
}
```

`interval` 的单位是毫秒，必须大于 `0`。

## 连接类型

### HTTP

在 `url` 指定的地址提供 HTTP API。支持 `GET` 和 `POST /:action`。

```json
{
  "type": "HTTP",
  "url": "http://127.0.0.1:3000"
}
```

### HTTP POST

把事件推送到 Webhook。可以设置请求超时和 HMAC-SHA1 签名密钥。

```json
{
  "type": "HTTPPost",
  "url": "http://127.0.0.1:8080/onebot",
  "timeout": 5,
  "secret": ""
}
```

`timeout` 为 `0` 时不设置超时，`secret` 留空时不签名。

### 正向 WebSocket

监听 WebSocket 服务，供 OneBot 客户端主动连接。

```json
{
  "type": "ForwardWebSocket",
  "url": "ws://127.0.0.1:5004"
}
```

### 反向 WebSocket

主动连接 OneBot 服务端。API 和事件可以分开连接，也可以使用 Universal 客户端共用一条连接。

```json
{
  "type": "ReverseWebSocket",
  "url": "ws://127.0.0.1:8080",
  "api_url": "",
  "event_url": "",
  "use_universal_client": false,
  "reconnect_interval": 3000
}
```

`api_url` 和 `event_url` 留空时使用 `url`。`reconnect_interval` 的单位是毫秒。
