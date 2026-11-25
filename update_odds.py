import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").rstrip("/")

# Futbol için normal süre + duraklama/uzatma payı (dakika)
MAX_CANLI_SURE_DK = 110

def simdi_utc():
    return datetime.now(timezone.utc)

def parse_iso_utc(dt_str):
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def mac_durumu_hesapla(commence_time_str):
    """
    Döner: (canli: bool, bitti: bool, dakika_metni: str, saat_tr: str)
    """
    baslangic = parse_iso_utc(commence_time_str)
    if not baslangic:
        return False, False, "", ""

    saat_tr = baslangic.astimezone(timezone(timedelta(hours=3))).strftime("%H:%M")
    simdi = simdi_utc()
    gecen_sn = (simdi - baslangic).total_seconds()

    if gecen_sn < 0:
        return False, False, "", saat_tr

    gecen_dk = int(gecen_sn // 60)

    # Standart maç süresini aşan maçları bitmiş sayıp bültenden çıkarıyoruz
    if gecen_dk > MAX_CANLI_SURE_DK:
        return False, True, "", saat_tr

    # 0-45 ilk yarı, 45-60 devre arası/ikinci yarı geçişi, 60-90+ ikinci yarı gösterimi
    if gecen_dk <= 45:
        dk_str = f"{max(1, gecen_dk)}'"
    elif gecen_dk <= 60:
        dk_str = f"İY / {gecen_dk}'"
    else:
        dk_str = f"{gecen_dk}'"

    return True, False, dk_str, saat_tr

BULTEN_VERISI = {
    "tarih": simdi_utc().strftime("%Y-%m-%d"),
    "secimler": [
        {
            "mac": "Barcelona - Chelsea (22:00)",
            "canli": True,
            "bitti": False,
            "dakika": "14'",
            "baslangic_saati": "22:00",
            "spor": "Futbol",
            "pazar": "Maç Sonucu",
            "tahmin": "MS 1",
            "oran": 1.62,
            "gemini_guven": 86,
            "claude_guven": 84,
            "not": "Yedek bülten verisi (Canlı maç örnek dakikası).",
            "secenek_guvenleri": {"MS 1": 86, "MS X": 80, "MS 2": 81},
            "oranlar": {"MS 1": 1.62, "MS X": 3.85, "MS 2": 4.90}
        },
        {
            "mac": "Galatasaray - Porto (23:00)",
            "canli": False,
            "bitti": False,
            "dakika": "",
            "baslangic_saati": "23:00",
            "spor": "Futbol",
            "pazar": "Maç Sonucu",
            "tahmin": "MS 1",
            "oran": 1.75,
            "gemini_guven": 85,
            "claude_guven": 83,
            "not": "Henüz başlamamış maç.",
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

    print("API'den gelen toplam mac sayisi:", len(games) if isinstance(games, list) else 0)

    secimler = []
    for g in (games or []):
        home = g.get("home_team", "Ev")
        away = g.get("away_team", "Deplasman")
        spor_adi = g.get("sport_title") or g.get("sport_key") or "Spor"
        commence = g.get("commence_time", "")

        canli, bitti, dk_str, saat_tr = mac_durumu_hesapla(commence)
        if bitti:
            continue

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
                "bitti": False,
                "dakika": dk_str,
                "baslangic_saati": saat_tr,
                "spor": spor_adi,
                "pazar": "Maç Sonucu",
                "tahmin": ilk_secim,
                "oran": oranlar[ilk_secim],
                "gemini_guven": 85,
                "claude_guven": 83,
                "not": f"{spor_adi} • Canli API verisi",
                "secenek_guvenleri": {k: 85 for k in oranlar},
                "oranlar": oranlar
            })

        if len(secimler) >= 20:
            break

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
