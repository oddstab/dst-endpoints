# dst-endpoints

[繁體中文](README.md) ｜ [English](README.en.md) ｜ [简体中文](README.zh-CN.md)

Don't Starve Together 客户端会调用的所有 Klei HTTP 接口，以及它们**现在**实际会返回什么。

不是从文档抄的，是从 `dontstarve_steam_x64.exe`（build `762172`）反汇编找出接口，
再用真实账号一个一个调用并记录结果。

## 内容

| 文件 | 说明 |
|---|---|
| [ENDPOINTS.md](ENDPOINTS.md) | 完整清单：方法、路径、判定、实际响应 |
| [results.json](results.json) | 全部探测的原始结果 |
| [auth_matrix.json](auth_matrix.json) | 每个接口使用哪个认证字段的矩阵 |
| `probe.py` | 全量探测脚本 |
| `probe_matrix.py` | 认证字段矩阵脚本 |

## 判读方式

Klei 的 API **一律返回 HTTP 200**，错误放在 body 里。只看状态码会被骗。

| 判定 | 意思 |
|---|---|
| **WORKS** | 调用成功，有真实数据或 `"Error": false` |
| **EXISTS** | 路由活着，但我们的输入被拒绝（结构化错误或需要认证） |
| **UNCONFIRMED** | 返回 500，而这台主机对「不存在的路径」也返回 500，所以无法证明 |
| **GONE** | 可执行文件里有这个路径，服务器返回 404，已经下线 |
| **HOST DEAD** | DNS 或连接失败 |

这个判定方式来自两个对照组：`/login/ThisPathIsNotReal` 与 `/lobby/ThisPathIsNotReal`
都返回 404，但 `/clientitems/DST/ThisPathIsNotReal` 返回 500——所以 items 主机需要另一套判准。

## 几个重点

- **login 主机只剩 4 条路由活着**：`LoginViaSteam`、`TokenPurpose`、`GameSessionToken`
  （都可用）与 `ServerLoginTokenViaSteam`（存在但需要认证）。改密码、注册、登出、
  找回密码、举报在可执行文件里都还有字符串，但服务器一律返回 404。
- **认证字段有两套**：`Tick`／`ValidateItems`／`OpenMysteryBox`／`RedeemCode`／
  `gameevents/*` 使用 `Token`；`GetAllItems`／`DailyGift`／`SetItemOpened`／`iap/*` 使用
  `ClientToken`。两者是同一个 token 字符串，只是 JSON 键名不同，填错跟没填一样。
- **`ReportMission/*` 会发奖励**。实测 `SNOWBIRD_GAME` 送 `Score: 0` 就拿到一个
  `PROFILEFLAIR_SNOWBIRD`，其余三个因此没有再重试。
- 大厅 API 全部返回 `403 E_AUTH_FAILURE`，路由确认存在，但认证方式尚未找出。

## 自己跑一次

```bat
python probe.py            :: 全量探测，输出 results.json
python probe_matrix.py     :: 认证字段矩阵，输出 auth_matrix.json
```

需要 Windows、Steam 客户端开着、账号拥有 DST。脚本会自己找安装路径并用
`steam_api64.dll` 取票。任何可能改变账号或库存状态的接口，只会收到空的或故意错误的
payload；已知会发奖励的接口则完全不调用。

## 不做哪些

- 没有测会动到钱或物品的购买流程。
- 没有测 `LogoutAll`。
- 大厅（`/lobby/*`）的认证方式未解。

## 许可

MIT
