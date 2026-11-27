# Euler OneBot

用 Python 实现的 OneBot 11 服务，协议层基于 [Hiro QQ](https://github.com/HarcicYang/hiro-qq)。

*🖋この世界を正すことができるのは、私だけだ！*

![GPL-3.0](https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&style=flat-square)
![OneBot V11](https://img.shields.io/badge/OneBot-11-black?style=flat-square)

> [!CAUTION]
> 出现了一些特殊情况，在 2026 年 11 月 28 日 8:00 （UTC+8）前，您将无法在本项目提供的自建签名服务中创建账户或修改配置，日志记录也将不可用

## Why EulerOneBot ?

1. 超过90%代码系古法手搓；
2. 我敢让他每天都在我自己的账户上运行；
3. Hook方案所没有的性能：本项目直接使用协议库。

## 特点

本项目基本目的在于为曾经使用 Lagrange.OneBot 、在 Lagrange.OneBot 停止维护后暂时不愿迁移到 milky 或 期望基于协议库而非
hook 方案的 OneBot 实现的用户。

完整的 API、事件和消息段支持范围见 [OneBot 兼容范围](docs/compatibility.md)。

## 环境要求

预编译版本覆盖：

- Apple Silicon macOS
- Windows x64 / arm64
- 非 musl 的 Linux x64 / arm64

从源码运行需要：

- Python 3.11 或更高版本
- 与所选登录协议匹配的签名服务

## 快速开始

### 使用预编译版本

前往 [Actions](https://github.com/HarcicYang/EulerOneBot/actions/workflows/build_release.yaml) 下载对应平台的压缩包并运行。

首次启动会在可执行文件旁生成 `appconfig.json`。填写后重新启动即可。

### 从源码运行

```shell
git clone https://github.com/HarcicYang/EulerOneBot.git
cd EulerOneBot
uv sync
uv run euler.onebot
```

什么你不喜欢uv？

```shell
pip install .
euler.onebot
```

或：

```shell
python -m euleronebot
```

## 最小配置

首次启动会生成配置模板。一个只启用正向 WebSocket 的最小示例如下：

```json
{
  "$schema": "./appconfig.schema.json",
  "log_level": "INFO",
  "access_token": "",
  "api_workers": 4,
  "connections": [
    {
      "type": "ForwardWebSocket",
      "url": "ws://127.0.0.1:5004"
    }
  ],
  "login": {
    "uin": 1234567890,
    "protocol": "linux",
    "signer_url": "https://sign.lagrangecore.org",
    "signer_token": "YOUR_SIGNER_TOKEN"
  }
}
```

不要提交包含真实账号或签名 Token 的配置文件。连接类型、完整字段和默认值见 [配置](docs/configuration.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [配置](docs/configuration.md) | 完整配置、连接类型、心跳和事件兼容 |
| [登录与签名](docs/login.md) | 协议类型、签名服务、appinfo 和自定义 sign provider |
| [OneBot 兼容范围](docs/compatibility.md) | API、事件、消息段和通信方式 |
| [性能基准](docs/benchmark.md) | 基准方法、worker 扩展性和本机数据 |
| [开发](docs/development.md) | 依赖、测试、类型检查和 schema 生成 |

## 性能

在 `20 ms` 模拟 QQ RTT、4 个 API workers、8 个在途请求下，队列分发和 HTTP 群消息接口约为 `93–95 req/s`。
去掉 RTT 后，同一套分发链路约为 `10,000 req/s`。测试条件和不同 worker 数量的数据见 [性能基准](docs/benchmark.md)。

## 开发

```shell
uv sync
uv run pytest -q
uv run ruff check .
uv run pyrefly check
```

更多说明见 [开发文档](docs/development.md)。

## 许可

GPL-3.0-or-later

## 友情链接

- [Lagrange.Milky fork](https://github.com/gotohitori0221/Lagrange.Core)
