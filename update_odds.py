import os
import json
import urllib.request
from datetime import datetime, timezone

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").rstrip("/")

BULTEN_VERISI = {
    "tarih": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "secimler": [
        {
            "mac": "Sabah FK - Barcelona (20:45)",
            "pazar": "Handikaplı MS",
            "tahmin": "H2 (-1.5)",
            "oran": 1.38,
            "gemini_guven": 88,
            "claude_guven": 86,
            "not": "GitHub otomasyonu ile guncellendi.",
            "secenek_guvenleri": {"ÇŞ X-2": 92, "MS 2": 90, "1.5 Üst": 88, "H2 (-1.5)": 87, "H2 (-2)": 81},
            "oranlar": {"ÇŞ X-2": 1.03, "MS 2": 1.14, "1.5 Üst": 1.10, "H2 (-1.5)": 1.38, "H2 (-2)": 1.65}
        }
    ]
}

def oranlari_cek():
    bugun = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not ODDS_API_KEY:
        return {**BULTEN_VERISI, "tarih": bugun}

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        games = json.loads(resp.read().decode("utf-8"))

    secimler = []
    for g in games[:10]:
        home = g.get("home_team", "Ev")
        away = g.get("away_team", "Deplasman")
        oranlar = {}
        sec_oran = 1.35

        for bm in g.get("bookmakers", [])[:1]:
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for oc in mkt.get("outcomes", []):
                        price = float(oc.get("price", 1.35))
                        if oc.get("name") == home:
                            oranlar["MS 1"] = price
                            sec_oran = price
                        elif oc.get("name") == away:
                            oranlar["MS 2"] = price
                        elif oc.get("name") == "Draw":
                            oranlar["MS X"] = price

        if oranlar:
            ilk_secim = "MS 1" if "MS 1" in oranlar else next(iter(oranlar.keys()))
            secimler.append({
                "mac": f"{home} - {away}",
                "pazar": "Maç Sonucu",
                "tahmin": ilk_secim,
                "oran": oranlar[ilk_secim],
                "gemini_guven": 85,
                "claude_guven": 83,
                "not": "Canli API otomasyonu ile cekildi.",
                "secenek_guvenleri": {k: 85 for k in oranlar},
                "oranlar": oranlar
            })

    return {"tarih": bugun, "secimler": secimler or BULTEN_VERISI["secimler"]}

def firebase_yaz(veri):
    hedef = f"{FIREBASE_DB_URL}/bulten.json"
    govde = json.dumps(veri).encode("utf-8")
    req = urllib.request.Request(hedef, data=govde, method="PUT", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status

if __name__ == "__main__":
    durum = firebase_yaz(oranlari_cek())
    print("Firebase guncellendi, durum:", durum)
