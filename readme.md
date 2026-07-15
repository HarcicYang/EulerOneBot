# Euler OneBot

一个无聊的 OneBot 实现，完全使用 python 语言，基于 [lagrange-python](https://github.com/LagrangeDev/lagrange-python)

<img src="https://img.shields.io/badge/OneBot-11-black?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHAAAABwCAMAAADxPgR5AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAxQTFRF////29vbr6+vAAAAk1hCcwAAAAR0Uk5T////AEAqqfQAAAKcSURBVHja7NrbctswDATQXfD//zlpO7FlmwAWIOnOtNaTM5JwDMa8E+PNFz7g3waJ24fviyDPgfhz8fHP39cBcBL9KoJbQUxjA2iYqHL3FAnvzhL4GtVNUcoSZe6eSHizBcK5LL7dBr2AUZlev1ARRHCljzRALIEog6H3U6bCIyqIZdAT0eBuJYaGiJaHSjmkYIZd+qSGWAQnIaz2OArVnX6vrItQvbhZJtVGB5qX9wKqCMkb9W7aexfCO/rwQRBzsDIsYx4AOz0nhAtWu7bqkEQBO0Pr+Ftjt5fFCUEbm0Sbgdu8WSgJ5NgH2iu46R/o1UcBXJsFusWF/QUaz3RwJMEgngfaGGdSxJkE/Yg4lOBryBiMwvAhZrVMUUvwqU7F05b5WLaUIN4M4hRocQQRnEedgsn7TZB3UCpRrIJwQfqvGwsg18EnI2uSVNC8t+0QmMXogvbPg/xk+Mnw/6kW/rraUlvqgmFreAA09xW5t0AFlHrQZ3CsgvZm0FbHNKyBmheBKIF2cCA8A600aHPmFtRB1XvMsJAiza7LpPog0UJwccKdzw8rdf8MyN2ePYF896LC5hTzdZqxb6VNXInaupARLDNBWgI8spq4T0Qb5H4vWfPmHo8OyB1ito+AysNNz0oglj1U955sjUN9d41LnrX2D/u7eRwxyOaOpfyevCWbTgDEoilsOnu7zsKhjRCsnD/QzhdkYLBLXjiK4f3UWmcx2M7PO21CKVTH84638NTplt6JIQH0ZwCNuiWAfvuLhdrcOYPVO9eW3A67l7hZtgaY9GZo9AFc6cryjoeFBIWeU+npnk/nLE0OxCHL1eQsc1IciehjpJv5mqCsjeopaH6r15/MrxNnVhu7tmcslay2gO2Z1QfcfX0JMACG41/u0RrI9QAAAABJRU5ErkJggg==" alt="OneBot V11">
<img src="https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&color=lightrey" alt="GPL-3.0">

---

## WIP

本项目处于极早期开发阶段，如你所见，我只写了个位数（应该吧）的 commit （）

## 安装使用

1. clone 本项目;
2. 下载 `lagrange` (即 [lagrange-python](https://github.com/LagrangeDev/lagrange-python) 的 package 部分)，放在本项目
   `main.py`的同目录;
3. 运行，填写配置文件，签名要求与其他 Lagrange（V2） 系列项目相同，请自行解决;
4. 大功告成！

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
| get_stranger_info       | ❌    |
| get_friend_list         | ❌    |
| get_group_info          | ❌    |
| get_group_list          | ❌    |
| get_group_member_info   | ❌    |
| get_group_member_list   | ❌    |
| get_status              | ❌    |
| get_version_info        | ❌    |

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
| notice.group_increase    | 🚧   |
| notice.group_ban         | ✅    |
| notice.friend_add        | ❌    |
| notice.group_recall      | ✅    |
| notice.friend_recall     | ✅    |
| notice.notify.poke       | ❌    |
| notice.notify.lucky_king | ❌    |
| notice.notify.honor      | ❌    |
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