# 登录与签名

QQ 登录依赖协议参数和签名服务。相关字段都位于 `appconfig.json` 的 `login` 下，完整配置示例见 [配置](configuration.md)。

## 协议类型

`login.protocol` 用于选择内置客户端参数：

| 取值 | 说明 |
|------|------|
| `linux` | 默认，Linux QQ |
| `windows` | Windows QQ |
| `macos` | macOS QQ |
| `android_phone` | Android 手机 QQ 9.1.60 |
| `android_pad` | Android 平板 QQ 9.3.70 |

PC 和 Android 使用不同的封包参数。Android 协议必须搭配支持 Android 接口的签名服务，并且只支持密码登录，不支持扫码。Android 登录的风险控制结果也可能与 PC 不同，建议先使用小号验证。

登录密码写在 `login.password`，配置了密码就走密码登录，留空则走扫码登录；`login.protocol` 为 `android_phone` 或 `android_pad` 时必须填写，否则启动时直接报错。

Android 封包沿用了 Lagrange V2 的几项细节：

- SSO 保留头带 `MsgType = 32` 和 `NtCoreVersion = 100`。
- `0xFE1_2` 按 UIN 查询用户资料时放行，并把 `MsgType` 置为 `0`；`0xFE1_8` 按 UID 查询时仍使用 `32`。
- 文件相关 OIDB `0xE37_1700` 和 `0x6D9_4` 的保留字段为 `1`。

## 签名服务

登录时，关键数据包需要由签名服务签名。可以使用 [Lagrange SignApiGuide](https://github.com/LagrangeDev/SignApiGuide) 中列出的服务，也可以使用[本项目自建签名 API](https://api.harcic.me/api/sign/manage)。

本项目自建服务的注册大概是更简易的，只需要您登录 GitHub、设置 Owner QQ，然后创建 access key 并绑定 Bot QQ。

自建服务的配置示例：

```json
{
  "login": {
    "uin": 1234567890,
    "signer_url": "https://api.harcic.me",
    "signer_token": "YOUR_ACCESS_TOKEN"
  }
}
```

接入其他签名服务时，把 `signer_url` 和 `signer_token` 换成服务提供的信息。

### PC 协议

PC 登录把签名请求发到：

```text
{signer_url}/api/sign/sec-sign
```

### Android 协议

`android_phone` 和 `android_pad` 走 OICQ `0x810_9` 登录流程。签名服务需要同时支持以下接口：

- `{signer_url}/api/sign`：请求体包含 `uin`、`cmd`、`seq`、`buffer`、`guid`、`version`、`qua`，返回 `data.sign`、`data.token`、`data.extra`
- `{signer_url}/energy`：TLV 544
- `{signer_url}/get_tlv553`：TLV 553

缺少任一接口都可能导致 Android 登录失败。

## 从签名服务器获取 appinfo

`login.fetch_appinfo` 默认关闭。打开后，启动时会先向签名服务获取 appinfo；获取失败则回退到内置参数。

PC 查询地址：

```text
{signer_url}/api/sign/sec-sign/appinfo_v2
```

Android 查询地址：

```text
{signer_url}/api/sign/appinfo_v2
```

返回结构兼容 Lagrange V2，会读取 `data` 或 `value` 中的 `os`、`kernel`、`vendor_os`、`qua`、`current_version`、`pt_version`、`sso_version`、`package_name`、`app_id`、`sub_app_id`、`app_client_version`，以及 `sdk_info` 中的 `sdk_version`、`misc_bit_map`、`sub_sig_map`、`main_sig_map`。

开启后，`login.protocol` 只用于决定签名接口和内置回退参数。签名服务不提供 appinfo 接口时保持关闭即可。

```json
{
  "login": {
    "fetch_appinfo": true
  }
}
```

## 自定义 appinfo

不使用自定义协议时，不需要 `appinfo.json`，保持 `login.use_custom` 为 `false`。

使用自定义协议时：

```json
{
  "login": {
    "use_custom": true,
    "appinfo_path": "./appinfo.json"
  }
}
```

自定义参数可能和现有签名服务不兼容。这种情况下需要准备匹配协议的签名服务，并同步修改 `login.signer_url` 和 `login.signer_token`。

`appinfo.json` 的字段格式如下。示例使用 Linux 参数，其他客户端需要替换为对应版本：

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

## 自定义 sign provider

除了 HTTP 签名服务，也可以在当前进程内完成签名。把实现写入 `sign_provider.py`，该文件不纳入版本控制。

```json
{
  "login": {
    "use_custom_sign_provider": true,
    "sign_provider_path": "./sign_provider.py",
    "sign_provider_entry": "sign_provider"
  }
}
```

入口是工厂函数，由 hiro-qq 在每次连接时调用：

```python
def sign_provider(sign_url, uin, guid, qua):
    async def get_sign(cmd, seq, buf):
        # ...
        return {"sign": "<hex>", "token": "<hex>", "extra": "<hex>"}

    return get_sign
```

实现时注意：

- `sign_url` 是 `login.signer_url` 拼接 Token 后的地址。
- 每次 `run()` 都会重新调用工厂；文件本身只加载一次。
- 返回 `sign`、`token`、`extra` 三个十六进制字符串；返回空字典表示当前包不签名。
- nonce 与当前 Unix 秒绑定，需要实时获取，不能缓存。
- 工厂只有 `qua`，可以用 `V1_AND_` 前缀区分 Android 和 PC。

仓库根目录的 `sign_provider.py` 提供了一个纯 Python 实现，可以直接修改。
