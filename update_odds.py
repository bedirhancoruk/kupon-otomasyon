import os
import json
import urllib.request

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").rstrip("/")

BULTEN_VERISI = {
    "tarih": "2026-11-25",
    "secimler": [
        {
            "mac": "Sabah FK - Barcelona (20:45)",
            "pazar": "Handikaplı MS",
            "tahmin": "H2 (-1.5)",
            "oran": 1.38,
            "gemini_guven": 88,
            "claude_guven": 86,
            "not": "GitHub otomasyonu ile guncellendi.",
            "secenek_guvenleri": {"CS_X_2": 92, "MS_2": 90, "15_Ust": 88, "H2_eksi_15": 87, "H2_eksi_2": 81},
            "oranlar": {"CS_X_2": 1.03, "MS_2": 1.14, "15_Ust": 1.1, "H2_eksi_15": 1.38, "H2_eksi_2": 1.65}
        },
        {
            "mac": "Atletico Madrid - Viking FK (23:00)",
            "pazar": "İY / MS",
            "tahmin": "İY/MS 1/1",
            "oran": 1.45,
            "gemini_guven": 88,
            "claude_guven": 86,
            "not": "GitHub otomasyonu ile guncellendi.",
            "secenek_guvenleri": {"CS_1_X": 92, "MS_1": 90, "IY_MS_1_1": 87, "15_Ust": 85},
            "oranlar": {"CS_1_X": 1.05, "MS_1": 1.22, "IY_MS_1_1": 1.45, "15_Ust": 1.16}
        },
        {
            "mac": "Paris Saint-Germain - Roma (23:00)",
            "pazar": "Maç Sonucu",
            "tahmin": "MS 1",
            "oran": 1.36,
            "gemini_guven": 87,
            "claude_guven": 85,
            "not": "GitHub otomasyonu ile guncellendi.",
            "secenek_guvenleri": {"CS_1_X": 90, "15_Ust": 86, "MS_1": 86},
            "oranlar": {"CS_1_X": 1.08, "MS_1": 1.36, "15_Ust": 1.15}
        }
    ]
}

def oranlari_cek():
    if not ODDS_API_KEY:
        return BULTEN_VERISI

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
                            oranlar["MS_1"] = price
                            sec_oran = price
                        elif oc.get("name") == away:
                            oranlar["MS_2"] = price
                        elif oc.get("name") == "Draw":
                            oranlar["MS_X"] = price

        if oranlar:
            secimler.append({
                "mac": f"{home} - {away}",
                "pazar": "Maç Sonucu",
                "tahmin": "MS 1",
                "oran": sec_oran,
                "gemini_guven": 85,
                "claude_guven": 83,
                "not": "Canli API otomasyonu ile cekildi.",
                "secenek_guvenleri": {k: 85 for k in oranlar},
                "oranlar": oranlar
            })

    return {"tarih": "2026-11-25", "secimler": secimler or BULTEN_VERISI["secimler"]}

def firebase_yaz(veri):
    hedef = f"{FIREBASE_DB_URL}/bulten.json"
    govde = json.dumps(veri).encode("utf-8")
    req = urllib.request.Request(hedef, data=govde, method="PUT", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status

if __name__ == "__main__":
    durum = firebase_yaz(oranlari_cek())
    print("Firebase guncellendi, durum:", durum)
