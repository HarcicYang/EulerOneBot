# Euler OneBot

一个无聊的 OneBot 实现，完全使用 python 语言，基于 [lagrange-python](https://github.com/LagrangeDev/lagrange-python)

<img src="https://img.shields.io/badge/OneBot-11-black?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHAAAABwCAMAAADxPgR5AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAxQTFRF////29vbr6+vAAAAk1hCcwAAAAR0Uk5T////AEAqqfQAAAKcSURBVHja7NrbctswDATQXfD//zlpO7FlmwAWIOnOtNaTM5JwDMa8E+PNFz7g3waJ24fviyDPgfhz8fHP39cBcBL9KoJbQUxjA2iYqHL3FAnvzhL4GtVNUcoSZe6eSHizBcK5LL7dBr2AUZlev1ARRHCljzRALIEog6H3U6bCIyqIZdAT0eBuJYaGiJaHSjmkYIZd+qSGWAQnIaz2OArVnX6vrItQvbhZJtVGB5qX9wKqCMkb9W7aexfCO/rwQRBzsDIsYx4AOz0nhAtWu7bqkEQBO0Pr+Ftjt5fFCUEbm0Sbgdu8WSgJ5NgH2iu46R/o1UcBXJsFusWF/QUaz3RwJMEgngfaGGdSxJkE/Yg4lOBryBiMwvAhZrVMUUvwqU7F05b5WLaUIN4M4hRocQQRnEedgsn7TZB3UCpRrIJwQfqvGwsg18EnI2uSVNC8t+0QmMXogvbPg/xk+Mnw/6kW/rraUlvqgmFreAA09xW5t0AFlHrQZ3CsgvZm0FbHNKyBmheBKIF2cCA8A600aHPmFtRB1XvMsJAiza7LpPog0UJwccKdzw8rdf8MyN2ePYF896LC5hTzdZqxb6VNXInaupARLDNBWgI8spq4T0Qb5H4vWfPmHo8OyB1ito+AysNNz0oglj1U955sjUN9d41LnrX2D/u7eRwxyOaOpfyevCWbTgDEoilsOnu7zsKhjRCsnD/QzhdkYLBLXjiK4f3UWmcx2M7PO21CKVTH84638NTplt6JIQH0ZwCNuiWAfvuLhdrcOYPVO9eW3A67l7hZtgaY9GZo9AFc6cryjoeFBIWeU+npnk/nLE0OxCHL1eQsc1IciehjpJv5mqCsjeopaH6r15/MrxNnVhu7tmcslay2gO2Z1QfcfX0JMACG41/u0RrI9QAAAABJRU5ErkJggg==" alt="OneBot V11">
<img src="https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&color=lightrey" alt="GPL-3.0">

---

## 项目特点

本项目基本目的在于为曾经使用 Lagrange.OneBot 、在 Lagrange.OneBot 停止维护后暂时不愿迁移到 milky 或 期望基于协议库而非 hook 方案的 OneBot 实现的用户。

## 环境要求

- Python >= 3.11
- [lagrange-python](https://github.com/LagrangeDev/lagrange-python) [^1]
- Lagrange V2 签名服务（见[签名指南](https://github.com/LagrangeDev/SignApiGuide)）

## 安装与使用

### 方式一：作为独立应用运行

1. 克隆本项目：

   ```shell
   git clone https://github.com/HarcicYang/EulerOneBot.git
   cd EulerOneBot
   ```

2. 安装依赖：

   Euler OneBot 使用 uv，您可以如是设置：

   ```shell
   uv sync
   pip install .  # 若您不希望使用uv
   ```

3. 运行，首次启动会自动生成 `appconfig.json` 配置模板：
   ```shell
   uv run main.py
   python main.py  # 若您不希望使用uv
   ```

4.填写配置文件后重启即可。

## 配置文件

首次运行会自动生成 `appconfig.json`，编辑后重启。配置项如下：

```json
{
  "$schema": "./appconfig.schema.json",
  "log_level": "INFO",
  "log_nf": true,
  "access_token": "",
  "connections": [
    {
      "type": "ForwardWebSocket",
      "url": "ws://127.0.0.1:5004"
    }
  ],
  "login": {
    "uin": 0,
    "signer_url": "https://sign.lagrangecore.org",
    "signer_token": ""
  },
  "heartbeat": {
    "enabled": true,
    "interval": 15000
  }
}
```

仓库附有 `appconfig.schema.json`（由 `BotConfig` 模型自动生成，可通过 `python scripts/gen_schema.py` 重新生成）。
保留配置开头的 `$schema` 字段后，VS Code / IDEA 等编辑器即可获得自动补全与校验。
若模型有改动，CI 会校验 schema 文件与模型保持同步。

| 字段                 | 说明                                                                           |
| -------------------- | ------------------------------------------------------------------------------ |
| `log_level`          | 日志级别：`TRACE` / `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`        |
| `log_nf`             | 是否为日志输出启用 NerdFont                                                    |
| `access_token`       | 鉴权 Token，配置后 HTTP / 正向 WebSocket / 反向 WebSocket 需携带（空为不鉴权） |
| `connections`        | 通信连接列表（见下方连接类型）                                                 |
| `login.uin`          | QQ 账号（不要真的写0哦）                                                       |
| `login.signer_url`   | 签名服务地址                                                                   |
| `login.signer_token` | 签名服务 Token                                                                 |
| `heartbeat.enabled`  | 是否启用心跳                                                                   |
| `heartbeat.interval` | 心跳间隔（毫秒）                                                               |

### 已经支持的连接类型

| 连接类型       | `type` 值          | 说明                                                                                                     |
| -------------- | ------------------ | -------------------------------------------------------------------------------------------------------- |
| HTTP           | `HTTP`             | 在 `url` 指定的地址提供 HTTP API 服务（`GET`/`POST /:action`）                                           |
| HTTP POST      | `HTTPPost`         | 将事件上报到 `url` 指定的 Webhook，可配置 `secret` 签名与 `timeout`                                      |
| 正向 WebSocket | `ForwardWebSocket` | 在 `url` 指定的地址监听,提供 WebSocket 服务供 OneBot 客户端连接                                          |
| 反向 WebSocket | `ReverseWebSocket` | 主动连接 `url` 指定的服务端，可配置 `api_url`、`event_url`、`use_universal_client`、`reconnect_interval` |

每类连接可能有额外的配置字段（如 `ReverseWebSocket` 的 `api_url`、`event_url` 等），详见 `ForwardWebsocketConfig`、
`ReverseWebsocketConfig` 等 Pydantic 模型定义。

## 开发

Euler OneBot 使用 [uv](https://docs.astral.sh/uv/) 进行依赖与项目管理：

```shell
uv sync
```

## 支持情况

<details>
<summary>API 类型</summary>

| API 名称                | 支持状态 | 类型 |
| ----------------------- | -------- | ---- |
| send_private_msg        | ✅       | 标准 |
| send_group_msg          | ✅       | 标准 |
| send_msg                | ✅       | 标准 |
| delete_msg              | ✅       | 标准 |
| get_msg                 | ✅       | 标准 |
| get_forward_msg         | ✅       | 标准 |
| send_like               | ✅       | 标准 |
| set_group_kick          | ✅       | 标准 |
| set_group_ban           | ✅       | 标准 |
| set_group_whole_ban     | ✅       | 标准 |
| set_group_admin         | ✅       | 标准 |
| set_group_card          | ✅       | 标准 |
| set_group_name          | ✅       | 标准 |
| set_group_leave         | ✅       | 标准 |
| set_group_special_title | ✅       | 标准 |
| set_friend_add_request  | ✅       | 标准 |
| set_group_add_request   | ✅       | 标准 |
| get_login_info          | ✅       | 标准 |
| get_stranger_info       | ✅       | 标准 |
| get_friend_list         | ✅       | 标准 |
| get_group_info          | ✅       | 标准 |
| get_group_list          | ✅       | 标准 |
| get_group_member_info   | ✅       | 标准 |
| get_group_member_list   | ✅       | 标准 |
| get_cookies             | ✅       | 标准 |
| get_csrf_token          | ✅       | 标准 |
| get_status              | ❌       | 标准 |
| get_version_info        | ✅       | 标准 |
| send_poke               | ✅       | 扩展 |
| group_reaction          | ✅       | 扩展 |

</details>

<details>
<summary>事件类型</summary>

| 事件名称                 | 支持状态 | 类型 |
| ------------------------ | -------- | ---- |
| message.private          | ✅       | 标准 |
| message.group            | ✅       | 标准 |
| notice.group_upload      | ✅       | 标准 |
| notice.group_admin       | ✅       | 标准 |
| notice.group_decrease    | ✅       | 标准 |
| notice.group_increase    | ✅       | 标准 |
| notice.group_ban         | ✅       | 标准 |
| notice.friend_add        | ✅       | 标准 |
| notice.group_recall      | ✅       | 标准 |
| notice.friend_recall     | ✅       | 标准 |
| notice.notify.poke       | ✅       | 标准 |
| notice.notify.lucky_king | ❌       | 标准 |
| notice.notify.honor      | ❌       | 标准 |
| request.friend           | ✅       | 标准 |
| request.group            | ✅       | 标准 |
| meta_event.lifecycle     | ❌       | 标准 |
| meta_event.heartbeat     | ✅       | 标准 |
| notice.friend_upload     | ✅       | 扩展 |
| notice.reaction          | ✅       | 扩展 |

</details>

<details>
<summary>消息段类型</summary>

| 消息段类型 | 支持状态 | 类型 |
| ---------- | -------- | ---- |
| text       | ✅       | 标准 |
| at         | ✅       | 标准 |
| reply      | ✅       | 标准 |
| face       | ✅       | 标准 |
| poke       | ✅ API   | 标准 |
| node       | ✅       | 标准 |
| forward    | ✅       | 标准 |
| image      | ✅       | 标准 |
| record     | ✅       | 标准 |
| video      | 🚧       | 标准 |
| contact    | ❌       | 标准 |
| location   | ❌       | 标准 |
| music      | ❌       | 标准 |
| rps        | ❌       | 标准 |
| dice       | ❌       | 标准 |
| shake      | ❌       | 标准 |
| json       | ✅       | 标准 |
| xml        | ❌       | 标准 |
| mface      | ✅       | 扩展 |

</details>

<details>
<summary>通信方式</summary>

| 通信方式       | 支持状态 | 类型 |
| -------------- | -------- | ---- |
| HTTP           | ✅       | 标准 |
| HTTP POST      | ✅       | 标准 |
| 正向 WebSocket | ✅       | 标准 |
| 反向 WebSocket | ✅       | 标准 |

</details>

## 性能基准

在 i5-1135G7 / 16GB 上使用 `uv run python scripts/benchmark.py` 测得：

| 场景                          | 吞吐         |
| ----------------------------- | ------------ |
| HTTP 端到端（send_group_msg） | ~600 req/s   |
| 正向 WS 请求-响应（单连接）   | ~3,700 req/s |
| WS 事件推送                   | ~60,000 条/s |
| 队列分发（含 SQLite 入库）    | ~6,400 req/s |

内存占用：峰值约 80 MB (benchmark 数据), 静默状态 ～= 60 MB (观察数据)

---

[^1]:
    尽管这里的连接指向 [LagrangeDev](https://github.com/LagrangeDev)
    ，本仓库的依赖项中该包裹指向 [我自己的fork](https://github.com/HarcicYang/lagrange-python)
    ，这是因为我为了该项目，在fork中照葫芦画瓢做了一些自己的实现。因此，如果您安装了 LagrangeDev
    提供的包裹，该项目可能无法正常运行。
