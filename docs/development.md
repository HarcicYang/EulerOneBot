# 开发

项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖：

```shell
uv sync
```

## 常用命令

```shell
uv run pytest -q  # 运行测试
uv run ruff check .  # Ruff
uv run pyrefly check  # 类型检查
uv run python scripts/gen_schema.py  # 根据配置模型更新 JSON Schema

uv run python scripts/benchmark.py --rtt-ms 20  # 模拟 20 ms QQ RTT 运行性能基准
```

基准的详细结果和测试条件见 [性能基准](benchmark.md)。

## 原生依赖

部分环境中，安装签名和加密相关依赖需要 OpenSSL 和 Rust 开发环境。遇到构建失败时先检查这两项。

## 提交前检查

```shell
uv run pytest -q
uv run ruff check .
uv run pyrefly check
git diff --check
```

修改配置模型后还需要提交重新生成的 `appconfig.schema.json`。
