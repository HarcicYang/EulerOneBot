# Euler OneBot

一个无聊的 OneBot 实现，完全使用 python 语言，基于 [Hiro QQ](https://github.com/HarcicYang/hiro-qq)

![GPL-3.0](https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&style=flat-square)
![OneBot V11](https://img.shields.io/badge/OneBot-11-black?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHAAAABwCAMAAADxPgR5AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAxQTFRF////29vbr6+vAAAAk1hCcwAAAAR0Uk5T////AEAqqfQAAAKcSURBVHja7NrbctswDATQXfD//zlpO7FlmwAWIOnOtNaTM5JwDMa8E+PNFz7g3waJ24fviyDPgfhz8fHP39cBcBL9KoJbQUxjA2iYqHL3FAnvzhL4GtVNUcoSZe6eSHizBcK5LL7dBr2AUZlev1ARRHCljzRALIEog6H3U6bCIyqIZdAT0eBuJYaGiJaHSjmkYIZd+qSGWAQnIaz2OArVnX6vrItQvbhZJtVGB5qX9wKqCMkb9W7aexfCO/rwQRBzsDIsYx4AOz0nhAtWu7bqkEQBO0Pr+Ftjt5fFCUEbm0Sbgdu8WSgJ5NgH2iu46R/o1UcBXJsFusWF/QUaz3RwJMEgngfaGGdSxJkE/Yg4lOBryBiMwvAhZrVMUUvwqU7F05b5WLaUIN4M4hRocQQRnEedgsn7TZB3UCpRrIJwQfqvGwsg18EnI2uSVNC8t+0QmMXogvbPg/xk+Mnw/6kW/rraUlvqgmFreAA09xW5t0AFlHrQZ3CsgvZm0FbHNKyBmheBKIF2cCA8A600aHPmFtRB1XvMsJAiza7LpPog0UJwccKdzw8rdf8MyN2ePYF896LC5hTzdZqxb6VNXInaupARLDNBWgI8spq4T0Qb5H4vWfPmHo8OyB1ito+AysNNz0oglj1U955sjUN9d41LnrX2D/u7eRwxyOaOpfyevCWbTgDEoilsOnu7zsKhjRCsnD/QzhdkYLBLXjiK4f3UWmcx2M7PO21CKVTH84638NTplt6JIQH0ZwCNuiWAfvuLhdrcOYPVO9eW3A67l7hZtgaY9GZo9AFc6cryjoeFBIWeU+npnk/nLE0OxCHL1eQsc1IciehjpJv5mqCsjeopaH6r15/MrxNnVhu7tmcslay2gO2Z1QfcfX0JMACG41/u0RrI9QAAAABJRU5ErkJggg==&style=flat-square)


[友情链接 - Forked Lagrange.Milky](https://github.com/gotohitori0221/Lagrange.Core)

---

## Why EulerOneBot ?

1. 超过90%代码系古法手搓；
2. 我敢让他每天都在我自己的账户上运行；
3. Hook方案所没有的性能。

## 项目特点

本项目基本目的在于为曾经使用 Lagrange.OneBot 、在 Lagrange.OneBot 停止维护后暂时不愿迁移到 milky 或 期望基于协议库而非
hook 方案的 OneBot 实现的用户。

## 环境要求

若您使用：

- Apple M 系列或 A 系列芯片的 macOS 设备
- 几乎任何 Windows x64/arm64 设备
- 几乎任何非 musl 的 x64/arm64 Linux 发行版

则您可以跳过环境配置，前往 [actions](https://github.com/HarcicYang/EulerOneBot/actions/workflows/build_release.yaml)
下载打包的可执行文件。

- Python >= 3.11
- [Hiro QQ](https://github.com/Harcic/hiro-qq) [^1]
- 与所选协议匹配的签名服务（PC 和安卓的接口不一样，见[签名服务](#签名服务)，Lagrange 说明见 [SignApiGuide](https://github.com/LagrangeDev/SignApiGuide)）

## 安装与使用

### 方式一：使用预编译可执行文件（推荐）

前往 [Actions](https://github.com/HarcicYang/EulerOneBot/actions/workflows/build_release.yaml) 下载与您设备架构对应的产物（
`-linux-x64` / `-linux-arm64` / `-macos-arm64` / `-windows-x64` / `-windows-arm64`）并解压，随后运行：

```shell
./euler-onebot-<版本号>       # Linux / macOS（macOS 提供普通命令行程序）
euler-onebot-<版本号>.exe     # Windows
```

首次启动会在可执行文件旁自动生成 `appconfig.json` 配置模板并显示提示，填写后重启即可。源码运行时配置仍在当前目录生成。

### 方式二：从源码运行

1. 克隆本项目：

   ```shell
   git clone https://github.com/HarcicYang/EulerOneBot.git
   cd EulerOneBot
   ```

2. 安装依赖并运行（首次启动会自动生成 `appconfig.json`）：

   ```shell
   uv sync
   uv run main.py
   ```

   若您不希望使用 uv：

   ```shell
   pip install .
   python main.py
   ```

## 配置文件

首次运行会自动生成 `appconfig.json`，编辑后重启。配置项如下：

```json
{
  "$schema": "./appconfig.schema.json",
  "log_level": "INFO",
  "log_nf": true,
  "access_token": "",
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
示例里把四种连接类型都写了一遍，实际只保留自己要用的那条，其余删掉即可，`connections` 数组里可以同时存在多条。

仓库附有 `appconfig.schema.json`（由 `BotConfig` 模型自动生成，可通过 `python scripts/gen_schema.py` 重新生成）。
保留配置开头的 `$schema` 字段后，VS Code / IDEA 等编辑器即可获得自动补全与校验。
若模型有改动，CI 会校验 schema 文件与模型保持同步。

| 字段                   | 说明                                                                           |
|------------------------|--------------------------------------------------------------------------------|
| `$schema`              | schema 文件路径，只给编辑器做补全和校验用，程序解析时会忽略                    |
| `log_level`            | 日志级别：`TRACE` / `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`        |
| `log_nf`               | 是否为日志输出启用 NerdFont                                                    |
| `access_token`         | 鉴权 Token，配置后 HTTP / 正向 WebSocket / 反向 WebSocket 需携带（空为不鉴权） |
| `event_compatibility.reaction_event_type` | reaction 事件下发类型，可选 `reaction` 或 `group_msg_emoji_like` |
| `connections`          | 通信连接列表（见下方连接类型）                                                 |
| `login.uin`            | QQ 账号（不要真的写0哦）                                                       |
| `login.protocol`       | 协议类型：`linux` / `macos` / `windows` / `android_phone` / `android_pad`      |
| `login.fetch_appinfo`  | 是否在启动时从签名服务器获取协议参数，默认 `false`                             |
| `login.signer_url`     | 签名服务地址（见[签名服务](#签名服务)）                                         |
| `login.signer_token`   | 签名服务 access token                                                          |
| `login.use_custom`     | 是否加载自定义协议参数；设为 `true` 后读取 `appinfo_path` 指定的 JSON 文件     |
| `login.appinfo_path`   | 自定义协议参数文件路径，默认 `./appinfo.json`，相对当前工作目录                |
| `login.use_custom_sign_provider` | 是否改用自定义 sign provider；设为 `true` 后从 `sign_provider_path` 加载    |
| `login.sign_provider_path`       | 自定义 sign provider 文件路径，默认 `./sign_provider.py`，相对当前工作目录 |
| `login.sign_provider_entry`      | 该文件中作为入口的方法名，默认 `sign_provider`                            |
| `login.setup_watchdog` | 是否启用看门狗；连续 10 分钟没有处理事件时触发重新登录                         |
| `login.use_ipv6`       | 是否使用 IPv6 连接                                                             |
| `login.use_optimum`    | 是否启用最优服务器选择                                                         |
| `heartbeat.enabled`    | 是否启用心跳                                                                   |
| `heartbeat.interval`   | 心跳间隔（毫秒）                                                               |

`event_compatibility.reaction_event_type` 默认值为 `reaction`。设置为 `group_msg_emoji_like` 后，群表情回应事件的
`notice_type` 会使用该兼容名称，其余字段保持不变。

### 协议类型

`login.protocol` 决定用哪套客户端参数登录，目前内置这几套：

| 取值            | 说明                    |
|-----------------|-------------------------|
| `linux`         | 默认，PC 端 Linux QQ    |
| `windows`       | PC 端 Windows QQ        |
| `macos`         | PC 端 macOS QQ          |
| `android_phone` | 安卓手机 QQ 9.1.60      |
| `android_pad`   | 安卓平板 QQ 9.3.70      |

前三个用的是一类 PC 参数，后两个是这次补上的安卓实现，参数和封包细节参照 Lagrange V2：

- 每个 SSO 包的保留头都会带上 `MsgType = 32` 和 `NtCoreVersion = 100`；
- 拉用户资料时，用 uin 查的 `0xFE1_2` 单独放行，`MsgType` 置 0；用 uid 查的 `0xFE1_8` 仍然是 32；
- 文件相关的 OIDB（`0xE37_1700`、`0x6D9_4`）把保留字段填 1。

切协议不用改代码，改配置就行。不过有两件事得先想清楚：安卓协议必须搭配支持安卓接口的签名服务；登录走的还是通用 NT 登录流程，风控表现和 PC 端不一定一样，建议先拿小号试。

### 从签名服务器获取 appinfo

`login.fetch_appinfo` 是这次新加的开关，默认关着。打开以后，启动时会先向签名服务要一份 appinfo，拿到就直接用，拿不到就退回内置参数，不会因此登不上。

地址是在签名地址后面接 `/appinfo_v2`：PC 协议是 `{signer_url}/api/sign/sec-sign/appinfo_v2`，安卓协议是 `{signer_url}/api/sign/appinfo_v2`。返回结构和 Lagrange V2 一样，读 `data` 或 `value` 里的 `os`、`kernel`、`vendor_os`、`qua`、`current_version`、`pt_version`、`sso_version`、`package_name`、`app_id`、`sub_app_id`、`app_client_version`，以及 `sdk_info` 里的 `sdk_version`、`misc_bit_map`、`sub_sig_map`、`main_sig_map`。

开关打开之后，`login.protocol` 只剩两个作用：决定签名接口走哪一套，以及拉取失败时用哪套内置参数兜底。版本号、qua 这些以签名服务返回的为准。签名服务不提供这个接口的话，保持关闭就行。

### 签名服务

登录 QQ 时需要签名服务为关键数据包签名。除上面的示例所用的[Lagrange 提供的签名服务 `https://sign.lagrangecore.org`](https://github.com/LagrangeDev/SignApiGuide)，本项目也提供
[自建的签名 API](https://api.harcic.me/api/sign/manage)，目前的长时间测试没有遇到风控/踢出问题，注册应该是更加简单的。其步骤大致如下：

1. 登录您的 GitHub 账户;
2. 设置 Owner QQ;
3. 创建 access key 并绑定您的 Bot QQ。

```json
{
  "login": {
    "uin": 1234567890,
    "signer_url": "https://api.harcic.me",
    "signer_token": "YOUR_ACCESS_TOKEN"
  }
}
```

若需要接入其它签名服务，把 `signer_url` 与 `signer_token` 换成对应服务提供的信息即可。

选了 `android_phone` 或 `android_pad` 之后，请求会发到 `{signer_url}/api/sign`，请求体是 `uin`、`cmd`、`seq`、`buffer`、`guid`、`version`、`qua`，返回里从 `data.sign`、`data.token`、`data.extra` 读签名。PC 端还是原来的 `{signer_url}/api/sign/sec-sign`。如果签名服务只支持 PC 那套规范，切到安卓协议会直接卡在签名失败，这一点在换协议前先确认好。

### 自定义 appinfo.json

`appinfo.json` 是可选文件。不用自定义协议时，不需要创建它，保持 `login.use_custom` 为 `false`，程序会用 `login.protocol` 指定的内置参数。

如需使用自定义协议，请将下面的示例保存为本地 `appinfo.json`（或替换为目标客户端对应的参数），再在 `appconfig.json` 的
`login` 中启用自定义协议并填写该文件路径：

注意，自定义协议版本可能与前文提到的签名服务不兼容。遇到这种情况时，需要自行准备兼容的签名服务，并在 `login.signer_url`
和 `login.signer_token` 中填写对应配置。

```json
{
  "use_custom": true,
  "appinfo_path": "./appinfo.json"
}
```

`appinfo.json` 需要包含 Lagrange `AppInfo` 使用的字段。下面以项目当前内置的 Linux 协议参数展示完整格式；若要模拟其他客户端，请替换为与目标客户端版本匹配的参数：

```json
{
  "Os": "Linux",
  "Kernel": "Linux",
  "VendorOs": "linux",
  "CurrentVersion": "3.2.26-46494",
  "MiscBitmap": 32764,
  "PtVersion": "2.0.0",
  "SsoVersion": 19,
  "PackageName": "com.tencent.qq",
  "WtLoginSdk": "nt.wtlogin.0.0.1",
  "AppId": 1600001615,
  "SubAppId": 537345891,
  "AppIdQrCode": 13697054,
  "AppClientVersion": 46494,
  "MainSigMap": 169742560,
  "SubSigMap": 0,
  "NtLoginType": 1,
  "Qua": "V1_LNX_NQ_3.2.26_46494_GW_B"
}
```

### 自定义 sign provider

除了把 `signer_url` 指向一个 HTTP 签名服务，也可以直接在本进程内签名：把实现写进 `sign_provider.py`，
再在配置里打开开关。该文件不纳入版本控制，可以放心写入自己的算法。

```json
{
  "login": {
    "use_custom_sign_provider": true,
    "sign_provider_path": "./sign_provider.py",
    "sign_provider_entry": "sign_provider"
  }
}
```

入口方法是一个工厂，参数由 hiro-qq 在每次连接时传入，返回值是一个异步签名函数：

```python
def sign_provider(sign_url, uin, guid, qua):
    async def get_sign(cmd, seq, buf):
        # ...
        return {"sign": "<hex>", "token": "<hex>", "extra": "<hex>"}

    return get_sign
```

几个要点：

- `sign_url` 就是 `login.signer_url` 拼上 token 后的地址，用不用由你决定；`uin`、`guid`、`qua` 是当次连接的真实值。
- hiro-qq 每次 `run()` 都会重新调用工厂，所以启动阶段拿不到设备信息也不影响；文件本身只加载一次。
- 返回值需要 `sign` / `token` / `extra` 三个十六进制串，返回空 dict 表示这个包不签名。
- 算法里如果用到 nonce，它是与 `time(NULL)` 绑定的：必须自己取当前 Unix 秒，不能缓存。
- `sign_provider_entry` 填文件中定义的方法名，可以同时放多个实现按需切换。
- 这个工厂拿不到协议名，只有 `qua`。要在里面区分 PC 和安卓，按 `qua` 是不是 `V1_AND_` 开头判断就行。

仓库根目录已经放了一份可直接改的单文件实现（移植自 ntqq-pure-sign 的纯 Python 版），把它当起点即可。

### 已经支持的连接类型

| 连接类型       | `type` 值          | 说明                                                                                                     |
|----------------|--------------------|----------------------------------------------------------------------------------------------------------|
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
|-------------------------|----------|------|
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
| get_status              | ✅       | 标准 |
| get_version_info        | ✅       | 标准 |
| send_poke               | ✅       | 扩展 |
| group_reaction          | ✅       | 扩展 |
| upload_group_file       | ✅       | 扩展 |
| upload_private_file     | ✅       | 扩展 |
| get_group_file_url      | ✅       | 扩展 |
| get_private_file_url    | ✅       | 扩展 |

</details>

<details>
<summary>事件类型</summary>

| 事件名称                 | 支持状态 | 类型 |
|--------------------------|----------|------|
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
| notice.notify.lucky_king | Never    | 标准 |
| notice.notify.honor      | Never    | 标准 |
| request.friend           | ✅       | 标准 |
| request.group            | ✅       | 标准 |
| meta_event.lifecycle     | ✅       | 标准 |
| meta_event.heartbeat     | ✅       | 标准 |
| notice.friend_upload     | ✅       | 扩展 |
| notice.reaction          | ✅       | 扩展 |

</details>

<details>
<summary>消息段类型</summary>

| 消息段类型 | 支持状态     | 类型 |
|------------|--------------|------|
| text       | ✅           | 标准 |
| at         | ✅           | 标准 |
| reply      | ✅           | 标准 |
| face       | ✅           | 标准 |
| poke       | ✅           | 标准 |
| node       | ✅           | 标准 |
| forward    | ✅           | 标准 |
| image      | ✅           | 标准 |
| record     | ✅           | 标准 |
| video      | ✅           | 标准 |
| file       | ✅ Recv only | 扩展 |
| contact    | ❌           | 标准 |
| location   | ❌           | 标准 |
| music      | ❌           | 标准 |
| rps        | ✅           | 标准 |
| dice       | ✅           | 标准 |
| shake      | ❌           | 标准 |
| json       | ✅           | 标准 |
| xml        | ❌           | 标准 |
| mface      | ✅           | 扩展 |
| grey_tips  | ✅ Send only | 扩展 |

</details>

<details>
<summary>通信方式</summary>

| 通信方式       | 支持状态 | 类型 |
|----------------|----------|------|
| HTTP           | ✅       | 标准 |
| HTTP POST      | ✅       | 标准 |
| 正向 WebSocket | ✅       | 标准 |
| 反向 WebSocket | ✅       | 标准 |

</details>

## 性能基准

在 i5-1135G7 / 16GB 上使用 `uv run python scripts/benchmark.py` 测得：

| 场景                          | 吞吐         |
|-------------------------------|--------------|
| HTTP 端到端（send_group_msg） | ~600 req/s   |
| 正向 WS 请求-响应（单连接）   | ~3,700 req/s |
| WS 事件推送                   | ~60,000 条/s |
| 队列分发（含 SQLite 入库）    | ~6,400 req/s |

内存占用：峰值约 80 MB (benchmark 数据), 静默状态 ～= 60 MB (观察数据)

---

[^1]: 部分环境下，安装有关依赖库可能需要额外配置 openssl 和 rust 开发环境.
