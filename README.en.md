# dst-endpoints

[繁體中文](README.md) ｜ [English](README.en.md) ｜ [简体中文](README.zh-CN.md)

Every Klei HTTP endpoint the Don't Starve Together client references, and what each one
actually answers **today**.

None of this comes from documentation. The paths were extracted by disassembling
`dontstarve_steam_x64.exe` (build `762172`), then each one was called with a real account
and the response recorded.

## Contents

| File | What it is |
|---|---|
| [ENDPOINTS.md](ENDPOINTS.md) | The full catalogue: method, path, verdict, observed response |
| [results.json](results.json) | Raw sweep output |
| [auth_matrix.json](auth_matrix.json) | Which auth field each endpoint reads |
| `probe.py` | The sweep |
| `probe_matrix.py` | The auth-field matrix |

## How to read the verdicts

Klei answers **HTTP 200 for everything** and puts the failure in the body. Status codes alone
will mislead you.

| Verdict | Meaning |
|---|---|
| **WORKS** | Called successfully: real data, or `"Error": false` |
| **EXISTS** | Route is live but rejected our input (structured error, or auth required) |
| **UNCONFIRMED** | Returned 500, and this host returns 500 for paths that do not exist either |
| **GONE** | Path is in the binary, server returns 404 — retired |
| **HOST DEAD** | DNS or TCP failure |

Those categories come from two control probes: `/login/ThisPathIsNotReal` and
`/lobby/ThisPathIsNotReal` both return 404, while
`/clientitems/DST/ThisPathIsNotReal` returns 500 — so the items host needs a different test.

## Highlights

- **Only four login routes are still alive**: `LoginViaSteam`, `TokenPurpose` and
  `GameSessionToken` all work; `ServerLoginTokenViaSteam` exists but wants auth. Password
  change, account creation, logout, password recovery and user reporting are all still in the
  binary's string table and all return 404.
- **There are two auth fields.** `Tick`, `ValidateItems`, `OpenMysteryBox`, `RedeemCode` and
  `gameevents/*` read `Token`; `GetAllItems`, `DailyGift`, `SetItemOpened` and `iap/*` read
  `ClientToken`. It is the same token string — only the JSON key differs, and getting it wrong
  looks exactly like having no token.
- **`ReportMission/*` grants rewards.** `SNOWBIRD_GAME` with `Score: 0` returned an
  `ItemID` and the item really landed in the account, so the other three were not retried.
- Lobby routes all return `403 E_AUTH_FAILURE`. Route confirmed, credential not identified.

## Running it yourself

```bat
python probe.py            :: full sweep, writes results.json
python probe_matrix.py     :: auth-field matrix, writes auth_matrix.json
```

Windows, Steam running, account owning DST. The scripts locate the install themselves and mint
a ticket through `steam_api64.dll`. Anything that could change account or inventory state only
ever receives an empty or deliberately invalid payload, and endpoints known to grant rewards
are not called at all.

## Not covered

- Purchase and barter flows that would move money or items.
- `LogoutAll`.
- Lobby authentication.

## License

MIT
