"""Probe every Klei endpoint the DST client references, and record what it answers.

Read-only endpoints are called for real. Anything that could change account or inventory
state is only sent an empty or deliberately invalid payload, and endpoints that are known
to grant rewards are not called at all (they are marked in the list).

Usage:  python probe.py [--game "<DST install>"] [--out results.json]
"""
import argparse
import binascii
import ctypes
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
LOGIN = "https://login.kleientertainment.com"
ITEMS = "https://items.kleientertainment.com"
LOBBY = "https://lobby-v2.klei.com"


def find_game(explicit=None):
    cands = [explicit, os.environ.get("DST_DIR"), os.path.dirname(BASE)]
    try:
        import winreg
        steam = winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"), "SteamPath")[0]
        roots = [steam]
        vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            with open(vdf, encoding="utf-8", errors="replace") as f:
                roots += re.findall(r'"path"\s+"([^"]+)"', f.read())
        for r in roots:
            cands.append(os.path.join(r.replace("\\\\", "\\"), "steamapps", "common",
                                      "Don't Starve Together"))
    except OSError:
        pass
    cands += [r"C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together"]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "bin64", "steam_api64.dll")):
            return os.path.abspath(c)
    return None


def steam_ticket(game):
    dll = os.path.join(game, "bin64", "steam_api64.dll")
    work = os.path.join(BASE, "steamctx")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "steam_appid.txt"), "w") as f:
        f.write("322330")
    os.chdir(work)
    api = ctypes.WinDLL(dll)
    api.SteamAPI_Init.restype = ctypes.c_bool
    if not api.SteamAPI_Init():
        sys.exit("SteamAPI_Init failed -- is the Steam client running and the account owning DST?")
    api.SteamAPI_SteamUser_v021.restype = ctypes.c_void_p
    user = api.SteamAPI_SteamUser_v021()
    get = api.SteamAPI_ISteamUser_GetAuthSessionTicket
    get.restype = ctypes.c_uint32
    get.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                    ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    buf = ctypes.create_string_buffer(4096)
    size = ctypes.c_uint32(0)
    get(user, buf, 4096, ctypes.byref(size), None)
    return binascii.hexlify(buf.raw[:size.value]).decode().upper()


def call(method, url, body=None, headers=None, timeout=25):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def classify(status, raw):
    text = raw.decode("utf-8", "replace").strip()
    if status == -1:
        return "UNREACHABLE", text
    try:
        j = json.loads(text)
    except Exception:
        if status == 404:
            return "NOT FOUND", text[:100]
        return f"HTTP {status}", text[:100]
    if j.get("Error") is False:
        return "WORKS", json.dumps(j, ensure_ascii=False)[:220]
    if j.get("ErrorCode"):
        return "REACHABLE", j["ErrorCode"]
    if j.get("Error") is True:
        return "REACHABLE", "error without code"
    return f"HTTP {status}", text[:100]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()
    out_path = os.path.abspath(args.out)        # steam_ticket() changes cwd

    game = find_game(args.game)
    if not game:
        sys.exit("DST install not found; pass --game")
    with open(os.path.join(game, "version.txt"), encoding="utf-8") as f:
        build = f.read().strip()
    print(f"game={game} build={build}")

    hdr = {
        "User-Agent": f"DontStarveTogether/{build}",
        "Accept-Encoding": "deflate, gzip",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "charsets": "utf-8",
    }

    st, raw = call("POST", LOGIN + "/login/LoginViaSteam",
                   {"SteamTicket": steam_ticket(game), "appid": "322330",
                    "Game": "DontStarveTogether"}, hdr)
    login = json.loads(raw.decode())
    token, kuid = login["Token"], login["UserID"]
    print(f"token ok for {kuid}")

    def post(url, body):
        return ("POST", url, body, hdr)

    # Control probes: same shape, path that cannot exist. Tells us what 404 / 500 mean here.
    controls = [
        ("control", "login bogus path", post(LOGIN + "/login/ThisPathIsNotReal", {}), "calibration"),
        ("control", "items bogus path", post(ITEMS + "/clientitems/DST/ThisPathIsNotReal", {}), "calibration"),
        ("control", "lobby bogus path", post(LOBBY + "/lobby/ThisPathIsNotReal", {}), "calibration"),
    ]

    probes = [
        # ---- auth ----
        ("auth", "LoginViaSteam (no ticket)", post(LOGIN + "/login/LoginViaSteam", {}), "route only"),
        ("auth", "RegisterSteamAccount", post(LOGIN + "/login/RegisterSteamAccount", {}), "route only"),
        ("auth", "ServerLoginTokenViaSteam", post(LOGIN + "/login/ServerLoginTokenViaSteam", {}), "route only"),
        ("auth", "Login", post(LOGIN + "/login/Login", {}), "route only"),
        ("auth", "CreateAccount", post(LOGIN + "/login/CreateAccount", {}), "route only"),
        ("auth", "TokenPurpose", post(LOGIN + "/login/TokenPurpose", {"Token": token}), "route only"),
        ("auth", "ChangePassword", post(LOGIN + "/login/ChangePassword", {}), "empty payload only"),
        ("auth", "RegisterGameKey", post(LOGIN + "/login/RegisterGameKey", {}), "empty payload only"),
        ("auth", "RecoverPassword", post(LOGIN + "/login/RecoverPassword", {}), "route only"),
        ("auth", "ReportUser", post(LOGIN + "/login/ReportUser", {}), "empty payload only"),
        ("auth", "GameSessionToken", post(LOGIN + "/login/GameSessionToken", {"Token": token}), "route only"),
        ("auth", "auto", ("GET", LOGIN + "/login/auto/?Game=DontStarveTogether", None, hdr), "browser redirect"),

        # ---- items (read-only or invalid-payload only) ----
        ("items", "Tick", post(ITEMS + "/clientitems/DST/Tick", {"Token": token}), "live"),
        ("items", "GetAllItems", post(ITEMS + "/clientitems/DST/GetAllItems",
                                      {"ClientToken": token, "InventoryStateToken": "",
                                       "CheckTwitchEntitlements": True}), "live"),
        ("items", "DailyGift", post(ITEMS + "/clientitems/DST/DailyGift", {"ClientToken": token}), "live"),
        ("items", "ValidateItems", post(ITEMS + "/clientitems/DST/ValidateItems",
                                        {"Token": token, "KU": kuid, "ItemIDs": []}), "invalid payload"),
        ("items", "ValidateSignature", post(ITEMS + "/clientitems/DST/ValidateSignature",
                                            {"Token": token}), "empty payload only"),
        ("items", "GrantSkinDLCEntitlements", post(ITEMS + "/clientitems/DST/GrantSkinDLCEntitlements",
                                                   {"ClientToken": token}), "live"),
        ("items", "VerifyGiftingReceipt", post(ITEMS + "/clientitems/DST/VerifyGiftingReceipt",
                                               {"Token": token, "Receipts": []}), "empty receipts"),
        ("items", "OpenMysteryBox", post(ITEMS + "/clientitems/DST/OpenMysteryBox",
                                         {"Token": token, "item_id": 0}), "invalid id only"),
        ("items", "RedeemCode", post(ITEMS + "/clientitems/DST/RedeemCode",
                                     {"Token": token, "Code": "PROBE-INVALID"}), "invalid code"),
        ("items", "SetItemOpened", post(ITEMS + "/clientitems/DST/SetItemOpened",
                                        {"Token": token, "item_id": 0}), "invalid id only"),
        ("items", "KeyValuesSet", post(ITEMS + "/gameevents/DontStarveTogether/KeyValuesSet",
                                       {"Token": token}), "empty payload only"),
        ("items", "KeyValuesSetMulti", post(ITEMS + "/gameevents/DontStarveTogether/KeyValuesSetMulti",
                                            {"Token": token}), "empty payload only"),
        ("items", "KeyValuesGetMulti", post(ITEMS + "/gameevents/DontStarveTogether/KeyValuesGetMulti",
                                            {"Token": token, "Keys": []}), "empty payload only"),
        ("items", "gameevents/DST/GetStatus", post(ITEMS + "/gameevents/DST/GetStatus",
                                                   {"Token": token}), "live"),

        # ---- iap ----
        ("iap", "GetPricingInfo", post(ITEMS + "/iap/DST/GetPricingInfo", {"Token": token}), "live"),
        ("iap", "PurchaseCreate", post(ITEMS + "/iap/DST/PurchaseCreate", {"Token": token}), "empty payload only"),
        ("iap", "PurchaseComplete", post(ITEMS + "/iap/DST/PurchaseComplete", {"Token": token}), "empty payload only"),
        ("iap", "PurchaseWithCurrency", post(ITEMS + "/iap/DST/PurchaseWithCurrency", {"Token": token}), "empty payload only"),
        ("iap", "BarterGainItem", post(ITEMS + "/iap/DST/BarterGainItem", {"Token": token}), "empty payload only"),
        ("iap", "BarterLoseItem", post(ITEMS + "/iap/DST/BarterLoseItem", {"Token": token}), "empty payload only"),
        ("iap", "BarterDuplicateItems", post(ITEMS + "/iap/DST/BarterDuplicateItems", {"Token": token}), "live"),

        # ---- lobby ----
        ("lobby", "read", post(LOBBY + "/lobby/read", {}), "route only"),
        ("lobby", "getIP", ("GET", LOBBY + "/lobby/getIP", None, hdr), "live"),
        ("lobby", "write", post(LOBBY + "/lobby/write", {}), "empty payload only"),
        ("lobby", "update", post(LOBBY + "/lobby/update", {}), "empty payload only"),
        ("lobby", "delete", post(LOBBY + "/lobby/delete", {}), "empty payload only"),
        ("lobby", "keepAlive", post(LOBBY + "/lobby/keepAlive", {}), "empty payload only"),
        ("lobby", "regioncapabilities", ("GET", "https://lobby-v2-cdn.klei.com/regioncapabilities-v2.json",
                                         None, {"Accept": "application/json"}), "live"),

        # ---- other hosts (GET only, nothing injected) ----
        ("other", "motd", ("GET", "https://motd.klei.com/motd.json/?game=dst&platform=STEAM"
                                   "&locale=TW&lang=tchinese&version=" + build, None, {}), "live"),
        ("other", "metrics", ("GET", "https://dst.metrics.klei.com/write", None, {}), "reachability only"),
        ("other", "analysisCL", ("GET", "https://clientservice.kleientertainment.com/analysisCL", None, {}), "reachability only"),
        ("other", "analytics-staging", ("GET", "https://analytics-staging.office.kleientertainment.com/write", None, {}), "reachability only"),
        ("other", "games-feedback", ("GET", "https://games-feedback.klei.com/submit", None, {}), "reachability only"),
        ("other", "crash-reporter", ("GET", "http://crashes.klei.ca/submitCrash", None, {}), "reachability only"),
        ("other", "cloudfront", ("GET", "https://d21wmy1ql1e52r.cloudfront.net/", None, {}), "reachability only"),
        ("other", "s3 ds-motd", ("GET", "https://s3.amazonaws.com/ds-motd/", None, {}), "reachability only"),
        ("other", "ds-motd s3 alias", ("GET", "https://ds-motd.s3.amazonaws.com/", None, {}), "reachability only"),
        ("other", "klei-motd", ("GET", "https://klei-motd.klei.com/", None, {}), "reachability only"),
        ("other", "s3 ds-mod-language", ("GET", "https://s3.amazonaws.com/ds-mod-language/", None, {}), "reachability only"),
        ("other", "s3 dstbuilds", ("GET", "https://s3.amazonaws.com/dstbuilds/", None, {}), "reachability only"),
        ("other", "s3 kleifiles", ("GET", "https://s3-us-west-2.amazonaws.com/kleifiles/", None, {}), "reachability only"),
        ("other", "translation-mods", ("GET", "https://dst-translation-mods.klei.com/", None, {}), "reachability only"),
        ("other", "theforge", ("GET", "https://theforge.kleientertainment.com/", None, {}), "reachability only"),
        ("other", "appspot release", ("GET", "http://dontstarve-release.appspot.com/", None, {}), "reachability only"),
        ("other", "appspot dev", ("GET", "http://dontstarve-dev.appspot.com/", None, {}), "reachability only"),
        ("other", "accounts rewards", ("GET", "https://accounts.klei.com/account/rewards", None, {}), "browser page"),
    ]

    results = []
    for group, label, (method, url, body, hdrs), note in controls + probes:
        status, raw = call(method, url, body, hdrs)
        verdict, detail = classify(status, raw)
        print(f"{verdict:12s} {group:7s} {label:34s} {status:4d} {detail[:100]}", flush=True)
        results.append({"group": group, "name": label, "method": method, "url": url,
                        "note": note, "status": status, "verdict": verdict, "detail": detail})

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("\nsummary:", json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
