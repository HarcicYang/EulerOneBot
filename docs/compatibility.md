# OneBot 兼容范围

Euler OneBot 以 OneBot v11 为主要接口，并保留部分 Lagrange.OneBot、go-cqhttp、NapCat 和 Overflow 扩展。

## API

| API | 状态 | 类型 |
|-----|------|------|
| `send_private_msg` | 支持 | 标准 |
| `send_group_msg` | 支持 | 标准 |
| `send_msg` | 支持 | 标准 |
| `delete_msg` | 支持 | 标准 |
| `get_msg` | 支持 | 标准 |
| `get_forward_msg` | 支持 | 标准 |
| `send_like` | 支持 | 标准 |
| `set_group_kick` | 支持 | 标准 |
| `set_group_ban` | 支持 | 标准 |
| `set_group_whole_ban` | 支持 | 标准 |
| `set_group_admin` | 支持 | 标准 |
| `set_group_card` | 支持 | 标准 |
| `set_group_name` | 支持 | 标准 |
| `set_group_leave` | 支持 | 标准 |
| `set_group_special_title` | 支持 | 标准 |
| `set_friend_add_request` | 支持 | 标准 |
| `set_group_add_request` | 支持 | 标准 |
| `get_login_info` | 支持 | 标准 |
| `get_stranger_info` | 支持 | 标准 |
| `get_friend_list` | 支持 | 标准 |
| `get_group_info` | 支持 | 标准 |
| `get_group_list` | 支持 | 标准 |
| `get_group_member_info` | 支持 | 标准 |
| `get_group_member_list` | 支持 | 标准 |
| `get_cookies` | 支持 | 标准 |
| `get_csrf_token` | 支持 | 标准 |
| `get_status` | 支持 | 标准 |
| `get_version_info` | 支持 | 标准 |
| `send_group_forward_msg` | 支持 | 扩展 |
| `send_private_forward_msg` | 支持 | 扩展 |
| `send_poke` | 支持 | 扩展 |
| `group_reaction` | 支持 | 扩展 |
| `set_group_reaction` | 支持 | 扩展 |
| `set_group_sign` | 支持 | 扩展 |
| `send_group_sign` | 支持 | 扩展别名 |
| `set_essence_msg` | 支持 | 扩展 |
| `delete_essence_msg` | 支持 | 扩展 |
| `upload_group_file` | 支持 | 扩展 |
| `upload_private_file` | 支持 | 扩展 |
| `get_group_file_url` | 支持 | 扩展 |
| `get_private_file_url` | 支持 | 扩展 |

## 事件

| 事件 | 状态 | 类型 |
|------|------|------|
| `message.private` | 支持 | 标准 |
| `message.group` | 支持 | 标准 |
| `notice.group_upload` | 支持 | 标准 |
| `notice.group_admin` | 支持 | 标准 |
| `notice.group_decrease` | 支持 | 标准 |
| `notice.group_increase` | 支持 | 标准 |
| `notice.group_ban` | 支持 | 标准 |
| `notice.friend_add` | 支持 | 标准 |
| `notice.group_recall` | 支持 | 标准 |
| `notice.friend_recall` | 支持 | 标准 |
| `notice.notify.poke` | 支持 | 标准 |
| `notice.notify.lucky_king` | 未支持 | 标准 |
| `notice.notify.honor` | 未支持 | 标准 |
| `request.friend` | 支持 | 标准 |
| `request.group` | 支持 | 标准 |
| `meta_event.lifecycle` | 支持 | 标准 |
| `meta_event.heartbeat` | 支持 | 标准 |
| `notice.friend_upload` | 支持 | 扩展 |
| `notice.reaction` | 支持 | 扩展 |
| `notice.group_msg_emoji_like` | 支持 | 扩展别名 |

`notice.group_msg_emoji_like` 通过 [`event_compatibility.reaction_event_type`](configuration.md#事件兼容) 启用。

## 消息段

| 消息段 | 状态 | 类型 |
|--------|------|------|
| `text` | 收发支持 | 标准 |
| `at` | 收发支持 | 标准 |
| `reply` | 收发支持 | 标准 |
| `face` | 收发支持 | 标准 |
| `poke` | 收发支持 | 标准 |
| `node` | 收发支持 | 标准 |
| `forward` | 收发支持 | 标准 |
| `image` | 收发支持 | 标准 |
| `record` | 收发支持 | 标准 |
| `video` | 收发支持 | 标准 |
| `file` | 仅接收 | 扩展 |
| `rps` | 收发支持 | 标准 |
| `dice` | 收发支持 | 标准 |
| `json` | 收发支持 | 标准 |
| `mface` | 收发支持 | 扩展 |
| `grey_tips` | 仅发送 | 扩展 |
| `contact` | 未支持 | 标准 |
| `location` | 未支持 | 标准 |
| `music` | 未支持 | 标准 |
| `shake` | 未支持 | 标准 |
| `xml` | 未支持 | 标准 |

## 通信方式

| 通信方式 | 状态 | 类型 |
|----------|------|------|
| HTTP | 支持 | 标准 |
| HTTP POST | 支持 | 标准 |
| 正向 WebSocket | 支持 | 标准 |
| 反向 WebSocket | 支持 | 标准 |

连接配置见 [配置](configuration.md#连接类型)。
