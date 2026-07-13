# Euler OneBot

一个无聊的 OneBot 实现，完全使用 python 语言，基于 [lagrange-python](https://github.com/LagrangeDev/lagrange-python)

---
## WIP

本项目处于极早期开发阶段，如你所见，我只写了个位数（应该吧）的 commit （）

## 安装使用

1. clone 本项目;
2. 下载 `lagrange` (即 [lagrange-python](https://github.com/LagrangeDev/lagrange-python) 的 package 部分)，放在本项目`main.py`的同目录;
3. 运行，填写配置文件，签名要求与其他 Lagrange（V2） 系列项目相同，请自行解决;
4. 大功告成！


## 支持情况

<details>
<summary>API 类型</summary>

| API 名称                  | 支持状态 |
|-------------------------|------|
| send_private_msg        | [x]  |
| send_group_msg          | [x]  |
| send_msg                | [x]  |
| delete_msg              | [x]  |
| get_msg                 | [ ]  |
| get_forward_msg         | [ ]  |
| send_like               | [ ]  |
| set_group_kick          | [ ]  |
| set_group_ban           | [ ]  |
| set_group_whole_ban     | [ ]  |
| set_group_admin         | [ ]  |
| set_group_card          | [ ]  |
| set_group_name          | [ ]  |
| set_group_leave         | [ ]  |
| set_group_special_title | [ ]  |
| set_friend_add_request  | [ ]  |
| set_group_add_request   | [ ]  |
| get_login_info          | [ ]  |
| get_stranger_info       | [ ]  |
| get_friend_list         | [ ]  |
| get_group_info          | [ ]  |
| get_group_list          | [ ]  |
| get_group_member_info   | [ ]  |
| get_group_member_list   | [ ]  |
| get_status              | [ ]  |
| get_version_info        | [ ]  |

</details>

<details>
<summary>事件类型</summary>

| 事件名称                     | 支持状态 |
|--------------------------|------|
| message.private          | [x]  |
| message.group            | [x]  |
| notice.group_upload      | [ ]  |
| notice.group_admin       | [ ]  |
| notice.group_decrease    | [ ]  |
| notice.group_increase    | [ ]  |
| notice.group_ban         | [ ]  |
| notice.friend_add        | [ ]  |
| notice.group_recall      | [ ]  |
| notice.friend_recall     | [ ]  |
| notice.notify.poke       | [ ]  |
| notice.notify.lucky_king | [ ]  |
| notice.notify.honor      | [ ]  |
| request.friend           | [ ]  |
| request.group            | [ ]  |
| meta_event.lifecycle     | [ ]  |
| meta_event.heartbeat     | [x]  |

</details>

<details>
<summary>消息段类型</summary>

| 消息段类型    | 支持状态 |
|----------|------|
| text     | [x]  |
| at       | [x]  |
| reply    | [x]  |
| face     | [x]  |
| poke     | [ ]  |
| mface    | [x]  |
| node     | [ ]  |
| forward  | [ ]  |
| image    | [x]  |
| record   | [x]  |
| video    | [x]  |
| contact  | [ ]  |
| location | [ ]  |
| music    | [ ]  |
| custom   | [ ]  |
| redbag   | [ ]  |
| rps      | [ ]  |
| dice     | [ ]  |
| shake    | [ ]  |
| json     | [ ]  |
| xml      | [ ]  |
| markdown | [ ]  |

</details>

<details>
<summary>通信方式</summary>

| 通信方式         | 支持状态 |
|--------------|------|
| HTTP         | [ ]  |
| HTTP Webhook | [ ]  |
| 正向 WebSocket | [x]  |
| 反向 WebSocket | [ ]  |

</details>