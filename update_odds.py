import os
import json
import urllib.request
from datetime import datetime, timezone

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").rstrip("/")

def simdi_utc():
    return datetime.now(timezone.utc)

def mac_canli_mi(commence_time_str):
    if not commence_time_str:
        return False
    try:
        iso_str = commence_time_str.replace("Z", "+00:00")
        baslangic = datetime.fromisoformat(iso_str)
        if baslangic.tzinfo is None:
            baslangic = baslangic.replace(tzinfo=timezone.utc)
        return simdi_utc() >= baslangic
    except Exception:
        return False

def saat_formatla_tr(commence_time_str):
    if not commence_time_str:
        return ""
    try:
        iso_str = commence_time_str.replace("Z", "+00:00")
        baslangic = datetime.fromisoformat(iso_str).astimezone(timezone(timedelta(hours=3)))
        return baslangic.strftime("%H:%M")
    except Exception:
        return ""

from datetime import timedelta

BULTEN_VERISI = {
    "tarih": simdi_utc().strftime("%Y-%m-%d"),
    "secimler": [
        {
            "mac": "Barcelona - Chelsea (22:00)",
            "canli": True,
            "baslangic_saati": "22:00",
            "spor": "Futbol",
            "pazar": "Maç Sonucu",
            "tahmin": "MS 1",
            "oran": 1.62,
            "gemini_guven": 86,
            "claude_guven": 84,
            "not": "API anahtari bekleniyor veya yedek bulten aktif.",
            "secenek_guvenleri": {"MS 1": 86, "MS X": 80, "MS 2": 81},
            "oranlar": {"MS 1": 1.62, "MS X": 3.85, "MS 2": 4.90}
        },
        {
            "mac": "Galatasaray - Porto (23:00)",
            "canli": False,
            "baslangic_saati": "23:00",
            "spor": "Futbol",
            "pazar": "Maç Sonucu",
            "tahmin": "MS 1",
            "oran": 1.75,
            "gemini_guven": 85,
            "claude_guven": 83,
            "not": "API anahtari bekleniyor veya yedek bulten aktif.",
            "secenek_guvenleri": {"MS 1": 85, "MS X": 80, "MS 2": 80},
            "oranlar": {"MS 1": 1.75, "MS X": 3.60, "MS 2": 4.40}
        }
    ]
}

def oranlari_cek():
    bugun = simdi_utc().strftime("%Y-%m-%d")
    if not ODDS_API_KEY:
        print("UYARI: ODDS_API_KEY bos, yedek veri kullaniliyor.")
        return {**BULTEN_VERISI, "tarih": bugun}

    url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        games = json.loads(resp.read().decode("utf-8"))

    print("API'den gelen mac sayisi:", len(games) if isinstance(games, list) else 0)

    secimler = []
    for g in (games or [])[:15]:
        home = g.get("home_team", "Ev")
        away = g.get("away_team", "Deplasman")
        spor_adi = g.get("sport_title") or g.get("sport_key") or "Spor"
        commence = g.get("commence_time", "")
        canli = mac_canli_mi(commence)
        saat_tr = saat_formatla_tr(commence)

        oranlar = {}
        for bm in g.get("bookmakers", [])[:1]:
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for oc in mkt.get("outcomes", []):
                        price = float(oc.get("price", 1.35))
                        if oc.get("name") == home:
                            oranlar["MS 1"] = price
                        elif oc.get("name") == away:
                            oranlar["MS 2"] = price
                        elif oc.get("name") == "Draw":
                            oranlar["MS X"] = price

        if oranlar:
            ilk_secim = "MS 1" if "MS 1" in oranlar else next(iter(oranlar.keys()))
            mac_etiketi = f"{home} - {away}" + (f" ({saat_tr})" if saat_tr else "")
            secimler.append({
                "mac": mac_etiketi,
                "canli": canli,
                "baslangic_saati": saat_tr,
                "spor": spor_adi,
                "pazar": "Maç Sonucu",
                "tahmin": ilk_secim,
                "oran": oranlar[ilk_secim],
                "gemini_guven": 85,
                "claude_guven": 83,
                "not": f"{spor_adi} • Canli API verisi ile guncellendi.",
                "secenek_guvenleri": {k: 85 for k in oranlar},
                "oranlar": oranlar
            })

    if not secimler:
        print("UYARI: Canli oran listesi bos dondu, yedek veri yaziliyor.")
        return {**BULTEN_VERISI, "tarih": bugun}

    return {"tarih": bugun, "secimler": secimler}

def firebase_yaz(veri):
    hedef = f"{FIREBASE_DB_URL}/bulten.json"
    govde = json.dumps(veri).encode("utf-8")
    req = urllib.request.Request(hedef, data=govde, method="PUT", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status

if __name__ == "__main__":
    durum = firebase_yaz(oranlari_cek())
    print("Firebase guncellendi, durum:", durum)
