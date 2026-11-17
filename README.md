# dst-endpoints

[繁體中文](README.md) ｜ [English](README.en.md) ｜ [简体中文](README.zh-CN.md)

Don't Starve Together 用戶端會用到的所有 Klei HTTP 端點，以及它們**現在**實際會回什麼。

不是從說明文件抄的，是從 `dontstarve_steam_x64.exe`（build `762172`）反組譯找出端點，
再用真實帳號一支一支打過去記錄結果。

## 內容

| 檔案 | 說明 |
|---|---|
| [ENDPOINTS.md](ENDPOINTS.md) | 完整清單：方法、路徑、判定、實際回應 |
| [results.json](results.json) | 全部探測的原始結果 |
| [auth_matrix.json](auth_matrix.json) | 每個端點吃哪個認證欄位的矩陣 |
| `probe.py` | 全量探測腳本 |
| `probe_matrix.py` | 認證欄位矩陣腳本 |

## 判讀方式

Klei 的 API **一律回 HTTP 200**，錯誤放在 body 裡。只看狀態碼會被騙。

| 判定 | 意思 |
|---|---|
| **WORKS** | 呼叫成功，有真實資料或 `"Error": false` |
| **EXISTS** | 路由活著，但我們的輸入被拒（結構化錯誤或需要認證） |
| **UNCONFIRMED** | 回 500，而這台主機對「不存在的路徑」也回 500，所以無法證明 |
| **GONE** | 執行檔裡有這個路徑，伺服器回 404，已經下架 |
| **HOST DEAD** | DNS 或連線失敗 |

這個判定方式來自兩支對照組：`/login/ThisPathIsNotReal` 與 `/lobby/ThisPathIsNotReal`
都回 404，但 `/clientitems/DST/ThisPathIsNotReal` 回 500——所以 items 主機需要另一套判準。

## 幾個重點

- **login 主機只剩 4 條路由活著**：`LoginViaSteam`、`TokenPurpose`、`GameSessionToken`
  （都可用）與 `ServerLoginTokenViaSteam`（存在但需要認證）。改密碼、註冊、登出、
  忘記密碼、檢舉在執行檔裡都還有字串，但伺服器一律 404。
- **認證欄位有兩套**：`Tick`／`ValidateItems`／`OpenMysteryBox`／`RedeemCode`／
  `gameevents/*` 吃 `Token`；`GetAllItems`／`DailyGift`／`SetItemOpened`／`iap/*` 吃
  `ClientToken`。兩者是同一個 token 字串，只是 JSON 鍵名不同，填錯跟沒填一樣。
- **`ReportMission/*` 會發獎勵**。實測 `SNOWBIRD_GAME` 送 `Score: 0` 就拿到一個
  `PROFILEFLAIR_SNOWBIRD`，其餘三支因此沒有再重試。
- 大廳 API 全部回 `403 E_AUTH_FAILURE`，路由確認存在，但認證方式尚未找出。

## 自己跑一次

```bat
python probe.py            :: 全量探測，輸出 results.json
python probe_matrix.py     :: 認證欄位矩陣，輸出 auth_matrix.json
```

需要 Windows、Steam 用戶端開著、帳號擁有 DST。腳本會自己找安裝路徑並用
`steam_api64.dll` 取票。任何可能改變帳號或庫存狀態的端點，只會收到空白的或刻意錯的
payload；已知會發獎勵的端點則完全不呼叫。

## 不做什麼

- 沒有測會動到錢或物品的購買流程。
- 沒有測 `LogoutAll`。
- 大廳（`/lobby/*`）的認證方式未解。

## 授權

MIT
