# Euler OneBot

一个无聊的 OneBot 实现，完全使用 python 语言，基于 [lagrange-python](https://github.com/LagrangeDev/lagrange-python)

<img src="https://img.shields.io/badge/OneBot-11-black?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHAAAABwCAMAAADxPgR5AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAxQTFRF////29vbr6+vAAAAk1hCcwAAAAR0Uk5T////AEAqqfQAAAKcSURBVHja7NrbctswDATQXfD//zlpO7FlmwAWIOnOtNaTM5JwDMa8E+PNFz7g3waJ24fviyDPgfhz8fHP39cBcBL9KoJbQUxjA2iYqHL3FAnvzhL4GtVNUcoSZe6eSHizBcK5LL7dBr2AUZlev1ARRHCljzRALIEog6H3U6bCIyqIZdAT0eBuJYaGiJaHSjmkYIZd+qSGWAQnIaz2OArVnX6vrItQvbhZJtVGB5qX9wKqCMkb9W7aexfCO/rwQRBzsDIsYx4AOz0nhAtWu7bqkEQBO0Pr+Ftjt5fFCUEbm0Sbgdu8WSgJ5NgH2iu46R/o1UcBXJsFusWF/QUaz3RwJMEgngfaGGdSxJkE/Yg4lOBryBiMwvAhZrVMUUvwqU7F05b5WLaUIN4M4hRocQQRnEedgsn7TZB3UCpRrIJwQfqvGwsg18EnI2uSVNC8t+0QmMXogvbPg/xk+Mnw/6kW/rraUlvqgmFreAA09xW5t0AFlHrQZ3CsgvZm0FbHNKyBmheBKIF2cCA8A600aHPmFtRB1XvMsJAiza7LpPog0UJwccKdzw8rdf8MyN2ePYF896LC5hTzdZqxb6VNXInaupARLDNBWgI8spq4T0Qb5H4vWfPmHo8OyB1ito+AysNNz0oglj1U955sjUN9d41LnrX2D/u7eRwxyOaOpfyevCWbTgDEoilsOnu7zsKhjRCsnD/QzhdkYLBLXjiK4f3UWmcx2M7PO21CKVTH84638NTplt6JIQH0ZwCNuiWAfvuLhdrcOYPVO9eW3A67l7hZtgaY9GZo9AFc6cryjoeFBIWeU+npnk/nLE0OxCHL1eQsc1IciehjpJv5mqCsjeopaH6r15/MrxNnVhu7tmcslay2gO2Z1QfcfX0JMACG41/u0RrI9QAAAABJRU5ErkJggg==" alt="OneBot V11">
<img src="https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&color=lightrey" alt="GPL-3.0">

---

## 项目状态

本项目处于极早期开发阶段。虽然比较简陋，但核心功能已基本可用。

## 环境要求

- Python >= 3.10
- [lagrange-python](https://github.com/LagrangeDev/lagrange-python)（QQ NT 协议库）
- Lagrange V2 签名服务（见[签名指南](https://github.com/LagrangeDev/SignApiGuide)）

## 安装与使用

### 方式一：作为独立应用运行

1. 克隆本项目：
   ```shell
   git clone https://github.com/HarcicYang/EulerOneBot.git
   cd EulerOneBot
   ```

2. 安装依赖：
   ```shell
   pip install .
   ```

3. 下载 `lagrange`（[lagrange-python](https://github.com/LagrangeDev/lagrange-python) 的 package 部分），放在项目根目录
   `main.py` 同级。*（PyPI有，但是怎么说呢，更新有点慢）*

4. 运行，首次启动会自动生成 `appconfig.json` 配置模板：
   ```shell
   python main.py
   ```

5. 填写配置文件后重启即可。

### 方式二：作为 Python 库安装

从 `0.0.2` 版本开始，Euler OneBot 也作为独立的 PyPI Package 存在，可以安装后当作一个 OneBot 风格 API 的 NTQQ 协议库使用：

```shell
pip install euler-onebot
```

## 配置文件

首次运行会自动生成 `appconfig.json`，编辑后重启。配置项如下：

```json
{
  "log_level": "INFO",
  "log_nf": true,
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

| 字段                   | 说明                                                                 |
|----------------------|--------------------------------------------------------------------|
| `log_level`          | 日志级别：`TRACE` / `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `log_nf`             | 是否为日志输出启用 NerdFont                                                 |
| `connections`        | 通信连接列表（见下方连接类型）                                                    |
| `login.uin`          | QQ 账号（不要真的写0哦）                                                     |
| `login.signer_url`   | 签名服务地址                                                             |
| `login.signer_token` | 签名服务 Token                                                         |
| `heartbeat.enabled`  | 是否启用心跳                                                             |
| `heartbeat.interval` | 心跳间隔（毫秒）                                                           |

### 已经支持的连接类型

| 连接类型         | `type` 值           | 说明              |
|--------------|--------------------|-----------------|
| 正向 WebSocket | `ForwardWebSocket` | 主动连接 OneBot 客户端 |

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

| API 名称                  | 支持状态 |
|-------------------------|------|
| send_private_msg        | ✅    |
| send_group_msg          | ✅    |
| send_msg                | ✅    |
| delete_msg              | ✅    |
| get_msg                 | ✅    |
| get_forward_msg         | ❌    |
| send_like               | ❌    |
| set_group_kick          | ❌    |
| set_group_ban           | ❌    |
| set_group_whole_ban     | ❌    |
| set_group_admin         | ❌    |
| set_group_card          | ❌    |
| set_group_name          | ❌    |
| set_group_leave         | ❌    |
| set_group_special_title | ❌    |
| set_friend_add_request  | ❌    |
| set_group_add_request   | ❌    |
| get_login_info          | ❌    |
| get_stranger_info       | ✅    |
| get_friend_list         | ❌    |
| get_group_info          | ✅    |
| get_group_list          | ❌    |
| get_group_member_info   | ❌    |
| get_group_member_list   | ❌    |
| get_status              | ❌    |
| get_version_info        | ✅    |

</details>

<details>
<summary>事件类型</summary>

| 事件名称                     | 支持状态 |
|--------------------------|------|
| message.private          | ✅    |
| message.group            | ✅    |
| notice.group_upload      | ❌    |
| notice.group_admin       | ❌    |
| notice.group_decrease    | ✅    |
| notice.group_increase    | ✅    |
| notice.group_ban         | ✅    |
| notice.friend_add        | ❌    |
| notice.group_recall      | ✅    |
| notice.friend_recall     | ✅    |
| notice.notify.poke       | ✅    |
| notice.notify.lucky_king | ❌    |
| notice.notify.honor      | ❌    |
| notice.reaction          | ✅    |
| request.friend           | ❌    |
| request.group            | ❌    |
| meta_event.lifecycle     | ❌    |
| meta_event.heartbeat     | ✅    |

</details>

<details>
<summary>消息段类型</summary>

| 消息段类型    | 支持状态 |
|----------|------|
| text     | ✅    |
| at       | ✅    |
| reply    | ✅    |
| face     | ✅    |
| poke     | ❌    |
| mface    | ✅    |
| node     | ❌    |
| forward  | ❌    |
| image    | ✅    |
| record   | ✅    |
| video    | ✅    |
| contact  | ❌    |
| location | ❌    |
| music    | ❌    |
| custom   | ❌    |
| redbag   | ❌    |
| rps      | ❌    |
| dice     | ❌    |
| shake    | ❌    |
| json     | ❌    |
| xml      | ❌    |
| markdown | ❌    |

</details>

<details>
<summary>通信方式</summary>

| 通信方式         | 支持状态 |
|--------------|------|
| HTTP         | ❌    |
| HTTP Webhook | ❌    |
| 正向 WebSocket | ✅    |
| 反向 WebSocket | ❌    |

</details>
