"""Work out which auth field each items/gameevents endpoint accepts.

For every endpoint, the same empty payload is sent with Token, ClientToken and KU in
different combinations. The first variant that stops complaining about the token tells us
which field the endpoint actually reads. Nothing here can mutate state: every payload is
empty apart from the auth field.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import ITEMS, call, find_game, steam_ticket  # noqa: E402

LOGIN = "https://login.kleientertainment.com"

ENDPOINTS = [
    "clientitems/DST/Tick",
    "clientitems/DST/GetAllItems",
    "clientitems/DST/DailyGift",
    "clientitems/DST/ValidateItems",
    "clientitems/DST/ValidateSignature",
    "clientitems/DST/GrantSkinDLCEntitlements",
    "clientitems/DST/VerifyGiftingReceipt",
    "clientitems/DST/OpenMysteryBox",
    "clientitems/DST/RedeemCode",
    "clientitems/DST/SetItemOpened",
    "clientitems/DST/ReportUnknownItemType",
    "clientitems/DST/Swap",
    "gameevents/DontStarveTogether/KeyValuesSet",
    "gameevents/DontStarveTogether/KeyValuesSetMulti",
    "gameevents/DontStarveTogether/KeyValuesGetMulti",
    "gameevents/DST/GetStatus",
    "iap/DST/GetPricingInfo",
    "iap/DST/PurchaseCreate",
    "iap/DST/BarterDuplicateItems",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    args = ap.parse_args()
    game = find_game(args.game)
    if not game:
        sys.exit("DST install not found")
    with open(os.path.join(game, "version.txt"), encoding="utf-8") as f:
        build = f.read().strip()
    hdr = {"User-Agent": f"DontStarveTogether/{build}", "Accept-Encoding": "deflate, gzip",
           "Accept": "application/json", "Content-Type": "application/json",
           "charsets": "utf-8"}

    _, raw = call("POST", LOGIN + "/login/LoginViaSteam",
                  {"SteamTicket": steam_ticket(game), "appid": "322330",
                   "Game": "DontStarveTogether"}, hdr)
    j = json.loads(raw.decode())
    token, kuid = j["Token"], j["UserID"]

    variants = {
        "Token": {"Token": token},
        "ClientToken": {"ClientToken": token},
        "Token+KU": {"Token": token, "KU": kuid},
        "ClientToken+KU": {"ClientToken": token, "KU": kuid},
    }

    rows = []
    for ep in ENDPOINTS:
        cells = []
        for vname, body in variants.items():
            status, raw = call("POST", f"{ITEMS}/{ep}", body, hdr)
            text = raw.decode("utf-8", "replace")[:120]
            try:
                d = json.loads(text)
                if d.get("Error") is False:
                    cell = "OK"
                else:
                    cell = d.get("ErrorCode") or "error"
            except Exception:
                cell = f"HTTP {status}"
            cells.append(cell)
        best = next((n for n, c in zip(variants, cells) if c != "E_INVALID_TOKEN"), None)
        rows.append({"endpoint": ep, "cells": cells, "auth_field": best})
        print(f"{ep:52s} " + " | ".join(f"{c[:26]:26s}" for c in cells) +
              f" => {best or 'none'}")

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_matrix.json"),
              "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("\nheader:", " | ".join(variants))


if __name__ == "__main__":
    main()
