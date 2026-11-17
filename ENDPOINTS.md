# DST / Klei endpoint catalogue

Every HTTP endpoint the Don't Starve Together client references, and what each one actually
answers when you call it today.

- **Source binary:** `bin64/dontstarve_steam_x64.exe`, build `762172`,
  SHA-256 `08b254abad063db3943bf3f2c013d248f1eb500e32bf924e064843b9f3b3ba34`, x86-64 PE
- **Method:** strings in `.rdata`, matched against RIP-relative `lea` references in `.text`.
  The HTTP layer is statically linked libcurl behind a thin `HttpClient2` wrapper.
- **Probed:** 2026-11-17, from a real Steam account that owns the game.
- **Raw data:** [`results.json`](results.json), [`auth_matrix.json`](auth_matrix.json)

## Verdict legend

| Verdict | Meaning |
|---|---|
| **WORKS** | Called successfully. Real data came back, or `"Error": false`. |
| **EXISTS** | The route is live but rejected our input with a structured API error (`ErrorCode`) or an auth failure. Route confirmed, payload not. |
| **UNCONFIRMED** | HTTP 500. On the items host a guaranteed-bogus path also returns 500, so this proves nothing either way. |
| **GONE** | HTTP 404 for a path that is present in the client binary. The server no longer serves it. |
| **HOST DEAD** | DNS or TCP failure. |
| **NOT TESTED** | Deliberately skipped because calling it would end sessions or move items. |

Two calibration probes were used throughout: `POST /login/ThisPathIsNotReal` and
`POST /lobby/ThisPathIsNotReal` both return **404**, and `POST /clientitems/DST/ThisPathIsNotReal`
returns **500**. That asymmetry is why the items host needs a different test than the others.

> Klei's APIs always answer HTTP 200 and put the failure in the body
> (`{"Error":true,"ErrorCode":"E_INVALID_TOKEN"}`). Judging success by status code alone will
> mislead you.

---

## 1. Login — `https://login.kleientertainment.com`

Most of the paths in this family are dead. The client binary still contains them, but the
server answers 404, which means password login and account management have moved off this
host entirely.

| Method | Path | Verdict | Observed |
|---|---|---|---|
| POST | `/login/LoginViaSteam` | **WORKS** | 200, `{"Error":false,"Token":"pcl-sing^…","UserID":"KU_…","AnalyticsJWT":"…"}` |
| POST | `/login/TokenPurpose` | **WORKS** | 200, `Error:false`, minted a fresh `pcl-sing^…` token from an existing one |
| POST | `/login/GameSessionToken` | **WORKS** | 200, `Error:false`, minted a `pgs-sing^…` token (different prefix from the client token) |
| POST | `/login/ServerLoginTokenViaSteam` | **EXISTS** | 200, `E_NO_AUTH` with an empty body |
| POST | `/login/RegisterSteamAccount` | **GONE** | 404 |
| POST | `/login/Login` | **GONE** | 404 |
| POST | `/login/CreateAccount` | **GONE** | 404 |
| POST | `/login/ChangePassword` | **GONE** | 404 |
| POST | `/login/RegisterGameKey` | **GONE** | 404 |
| POST | `/login/RecoverPassword` | **GONE** | 404 |
| POST | `/login/ReportUser` | **GONE** | 404 |
| POST | `/login/Logout` | **GONE** | 404 |
| POST | `/login/LogoutAll` | **NOT TESTED** | would terminate every session on the account |
| GET | `/login/auto/?Game=DontStarveTogether` | **GONE** | 404 |

`LoginViaSteam` body, as captured from the running client:

```json
{"SteamTicket": "<Steam auth session ticket, uppercase %02X hex>",
 "appid": "322330",
 "Game": "DontStarveTogether"}
```

Missing `Game` returns `E_UNKNOWN_GAME`; a wrong `Game` value returns `E_INCORRECT_GAME`;
a ticket that Steam will not validate returns `E_INVALID_STEAM_TICKET`.

---

## 2. Items, inventory, events — `https://items.kleientertainment.com`

### 2a. Which auth field each endpoint reads

Both fields carry the *same* Klei token string. Only the JSON key differs, and getting it
wrong is indistinguishable from having no token at all.

| Endpoint family | Field |
|---|---|
| `Tick`, `ValidateItems`, `OpenMysteryBox`, `RedeemCode`, `gameevents/*` | `Token` |
| `GetAllItems`, `DailyGift`, `GrantSkinDLCEntitlements`, `SetItemOpened`, `iap/*` | `ClientToken` |

`Tick` with `ClientToken`, or `GetAllItems` with `Token`, returns `E_INVALID_TOKEN`.

### 2b. Endpoints

| Method | Path | Verdict | Observed |
|---|---|---|---|
| POST | `clientitems/DST/Tick` | **WORKS** | `{"Error":false,"GiftReceived":false}` — the drop-time heartbeat, sent every 360 s |
| POST | `clientitems/DST/GetAllItems` | **WORKS** | Full inventory, several thousand items |
| POST | `clientitems/DST/DailyGift` | **WORKS** | `{"Error":false,"GiftReceived":false}` |
| POST | `clientitems/DST/GrantSkinDLCEntitlements` | **WORKS** | `{"Error":false,"NewEntitlements":null,"AllEntitlements":null}` |
| POST | `clientitems/DST/SetItemOpened` | **WORKS** | With `item_id: 0` it echoed `ItemID:0, Modified:0` — a no-op. With a real id it consumes a gift box. |
| POST | `clientitems/DST/ValidateItems` | **EXISTS** | `E_INVALID_KU` |
| POST | `clientitems/DST/OpenMysteryBox` | **EXISTS** | `E_INVALID_ITEMID` |
| POST | `clientitems/DST/RedeemCode` | **EXISTS** | `E_INVALID_CODE` |
| POST | `clientitems/DST/Swap` | **EXISTS** | Auth accepted with `ClientToken`, then 500 on an empty payload |
| POST | `clientitems/DST/ReportMission/SNOWBIRD_GAME` | **WORKS** | Granted `PROFILEFLAIR_SNOWBIRD` — see the warning below |
| POST | `clientitems/DST/ReportMission/CROW_GAME` | **UNCONFIRMED** | 500 with the payload we used |
| POST | `clientitems/DST/ReportMission/CROWKID_GAME` | **UNCONFIRMED** | 500 |
| POST | `clientitems/DST/ReportMission/REDBIRD_GAME` | **UNCONFIRMED** | 500 |
| POST | `clientitems/DST/ValidateSignature` | **UNCONFIRMED** | 500 with empty and structurally valid payloads |
| POST | `clientitems/DST/VerifyGiftingReceipt` | **UNCONFIRMED** | 500 with `Receipts: []` and `Receipts: [{}]` |
| POST | `clientitems/DST/ReportUnknownItemType` | **UNCONFIRMED** | 500 with a plausible `ItemType` |
| POST | `gameevents/DontStarveTogether/KeyValuesSetMulti` | **WORKS** | `{}` |
| POST | `gameevents/DontStarveTogether/KeyValuesGetMulti` | **WORKS** | `{"Events":{}}` |
| POST | `gameevents/DontStarveTogether/KeyValuesSet` | **UNCONFIRMED** | 500; not retried because a success would write junk to the account |
| POST | `gameevents/DST/GetStatus` | **UNCONFIRMED** | 500 with no event, `Event:"DST"` and `EventHash` |

> **Warning about `ReportMission/*`.** These endpoints grant a reward. Calling
> `SNOWBIRD_GAME` with a score of 0 returned
> `{"Error":false,"Result":"DONE","ItemID":…,"ItemType":"PROFILEFLAIR_SNOWBIRD"}` and the item
> really was added to the account. The other three were not retried after that, which is why
> they stay unconfirmed.

---

## 3. In-app purchase and barter — same items host

| Method | Path | Verdict | Observed |
|---|---|---|---|
| POST | `iap/DST/GetPricingInfo` | **WORKS** | Returns `PricingHash` and the full `IAPDefs` catalogue |
| POST | `iap/DST/BarterDuplicateItems` | **WORKS** | `{"Error":false,"CurrencyName":"","RemovedItems":[]}` — nothing was consumed |
| POST | `iap/DST/PurchaseCreate` | **EXISTS** | Auth accepted with `ClientToken`, then 500 |
| POST | `iap/DST/PurchaseComplete` | **EXISTS** | Auth accepted, then 500 |
| POST | `iap/DST/PurchaseWithCurrency` | **EXISTS** | Auth accepted, then 500 |
| POST | `iap/DST/BarterGainItem` | **EXISTS** | Auth accepted, then 500 |
| POST | `iap/DST/BarterLoseItem` | **EXISTS** | Auth accepted, then 500 |

None of these were given a purchasable payload. The 500s are what you get before validation
reaches the point where money or items move.

---

## 4. Lobby and server browser — `https://lobby-v2.klei.com`

| Method | Path | Verdict | Observed |
|---|---|---|---|
| GET | `/lobby/getIP` | **WORKS** | `{"__addr":"<your public IP>"}` |
| POST | `/lobby/read` | **EXISTS** | 403 `{"Error":{"Code":"E_AUTH_FAILURE"}}` |
| POST | `/lobby/write` | **EXISTS** | 403 `E_AUTH_FAILURE` |
| POST | `/lobby/update` | **EXISTS** | 403 `E_AUTH_FAILURE` |
| POST | `/lobby/delete` | **EXISTS** | 403 `E_AUTH_FAILURE` |
| POST | `/lobby/keepAlive` | **EXISTS** | 403 `E_AUTH_FAILURE` |
| GET | `https://lobby-v2-cdn.klei.com/regioncapabilities-v2.json` | **WORKS** | Region list: `us-east-1`, `eu-central-1`, `ap-southeast-1`, `ap-east-1` |

`getIP` with `POST` returns 405 `E_HTTP_METHOD`, so the method matters.

The lobby routes want credentials we did not identify. A Klei client token in the body does not
satisfy them. Regional hosts follow the pattern `https://lobby-v2-<region>.klei.com`.

---

## 5. Everything else

| Endpoint | Verdict | Observed |
|---|---|---|
| `https://motd.klei.com/motd.json/?game=dst&platform=STEAM&locale=TW&lang=tchinese&version=<build>` | **WORKS** | 200 JSON. Omitting the query parameters returns 400 |
| `https://dst.metrics.klei.com/write` | **EXISTS** | 200 `{"Error":{"Code":"E_BAD_REQUEST"},"EventCount":0}` — GET is accepted, nothing was injected |
| `https://games-feedback.klei.com/submit` | **EXISTS** | 500 on GET; expects a POST body |
| `http://crashes.klei.ca/submitCrash` | **EXISTS** | 500 on GET; `CrashReporter.exe` posts to it |
| `https://d21wmy1ql1e52r.cloudfront.net/` | **EXISTS** | 403 `AccessDenied` |
| `https://s3.amazonaws.com/ds-motd/` | **EXISTS** | 403 `AccessDenied` (bucket exists, listing denied) |
| `https://ds-motd.s3.amazonaws.com/` | **EXISTS** | 403 |
| `https://klei-motd.klei.com/` | **EXISTS** | 403 |
| `https://s3.amazonaws.com/ds-mod-language/` | **EXISTS** | 403 |
| `https://s3.amazonaws.com/dstbuilds/` | **WORKS** | 200, returns a public `ListBucketResult` |
| `https://s3-us-west-2.amazonaws.com/kleifiles/` | **EXISTS** | 403 |
| `https://dst-translation-mods.klei.com/` | **EXISTS** | 403 |
| `https://accounts.klei.com/account/rewards` | **WORKS** | 200 HTML (Klei account page) |
| `https://clientservice.kleientertainment.com/analysisCL` | **HOST DEAD** | DNS NXDOMAIN |
| `https://analytics-staging.office.kleientertainment.com/write` | **HOST DEAD** | connection timeout |
| `https://theforge.kleientertainment.com/` | **HOST DEAD** | DNS NXDOMAIN |
| `http://dontstarve-release.appspot.com/` | **GONE** | 404 |
| `http://dontstarve-dev.appspot.com/` | **GONE** | 404 |
| `https://<region>.gsm.events.klei.ca` | **HOST DEAD** | did not resolve for any region name advertised by the lobby CDN |

---

## 6. What this catalogue does not cover

- **Lobby auth.** We know the routes exist and reject us, but not what credential satisfies
  them. That needs either a captured lobby request or more disassembly of the lobby client.
- **The 500 family.** `ValidateSignature`, `VerifyGiftingReceipt`, `ReportUnknownItemType`,
  `gameevents/KeyValuesSet` and `gameevents/DST/GetStatus` cannot be distinguished from
  non-existent routes on that host without a valid payload. The binary gives us their field
  names (`Digest`/`Signature`/`Version`, `Receipts`, …) but not values that validate.
- **Purchase flows.** Not exercised. A wrong call moves real money or items.
- **The three other `ReportMission` games.** Not called again after `SNOWBIRD_GAME` turned out
  to grant a reward.

## 7. Reproducing this

```bat
python probe.py            :: full sweep, writes results.json
python probe_matrix.py     :: auth-field matrix, writes auth_matrix.json
```

Both read the build number from `version.txt`, mint a Steam ticket through `steam_api64.dll`
and log in with `LoginViaSteam`. Steam must be running and the account must own the game.

The sweep only ever sends empty or deliberately invalid payloads to anything that could change
state, and skips the endpoints known to grant rewards.
