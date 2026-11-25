import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").rstrip("/")
TR_TZ = timezone(timedelta(hours=3))

MAX_CANLI_SURE_DK = 115

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

def dakika_etiketi_uret(gecen_dk):
    if gecen_dk < 1:
        return "1'"
    if gecen_dk <= 45:
        return f"{gecen_dk}'"
    if gecen_dk <= 60:
        return "İY"
    ikinci_yari_dk = gecen_dk - 15
    if ikinci_yari_dk <= 90:
        return f"{ikinci_yari_dk}'"
    return f"90+{ikinci_yari_dk - 90}'"

def mac_durumu_hesapla(commence_time_str):
    """
    Döner: (canli: bool, bitti: bool, dakika_metni: str, gecen_dk: int, saat_tr: str)
    """
    baslangic = parse_iso_utc(commence_time_str)
    if not baslangic:
        return False, False, "", 0, ""

    saat_tr = baslangic.astimezone(TR_TZ).strftime("%H:%M")
    simdi = simdi_utc()
    gecen_sn = (simdi - baslangic).total_seconds()

    if gecen_sn < 0:
        return False, False, "", 0, saat_tr

    gecen_dk = int(gecen_sn // 60)
    if gecen_dk > MAX_CANLI_SURE_DK:
        return False, True, "", gecen_dk, saat_tr

    return True, False, dakika_etiketi_uret(gecen_dk), gecen_dk, saat_tr

def orana_gore_guven(oran, canli, gecen_dk):
    """
    Oran ve canlı dakika bandına göre %72 - %93 arası güven puanı hesaplar.
    """
    try:
        o = float(oran)
    except Exception:
        o = 2.0

    if o <= 1.25:
        baz = 90
    elif o <= 1.45:
        baz = 87
    elif o <= 1.70:
        baz = 84
    elif o <= 2.05:
        baz = 80
    elif o <= 2.60:
        baz = 76
    else:
        baz = 72

    if not canli:
        return max(70, min(92, baz))

    # Canlı maçta dakika ilerledikçe süre riski ve tempo etkisi uygulanır
    if gecen_dk <= 15:
        dk_farki = -1
    elif gecen_dk <= 45:
        dk_farki = 1 if o <= 1.65 else -1
    elif gecen_dk <= 60:
        dk_farki = 2 if o <= 1.65 else 0
    elif gecen_dk <= 75:
        dk_farki = 1 if o <= 1.55 else -2
    else:
        dk_farki = -2 if o <= 1.50 else -4

    return max(70, min(93, baz + dk_farki))

def mac_analizi_olustur(home, away, oranlar, canli, gecen_dk, dk_str, spor_adi):
    secenek_guvenleri = {}
    for secim, oran_degeri in oranlar.items():
        secenek_guvenleri[secim] = orana_gore_guven(oran_degeri, canli, gecen_dk)

    # En yüksek güven puanına sahip seçeneği öne çıkar
    en_iyi_secim = max(secenek_guvenleri.items(), key=lambda x: x[1])[0]
    en_iyi_guven = secenek_guvenleri[en_iyi_secim]

    gemini_guven = max(70, min(94, en_iyi_guven + (1 if canli and gecen_dk <= 60 else 0)))
    claude_guven = max(70, min(93, en_iyi_guven - (1 if canli and gecen_dk > 75 else 0)))

    if canli:
        if gecen_dk <= 45:
            bolum_notu = f"İlk yarı ({dk_str}) canlı analizi"
        elif gecen_dk <= 60:
            bolum_notu = f"Devre arası ({dk_str}) canlı analizi"
        elif gecen_dk <= 75:
            bolum_notu = f"İkinci yarı ({dk_str}) canlı analizi"
        else:
            bolum_notu = f"Son bölüm ({dk_str}) temkinli canlı analizi"
        not_metni = f"{bolum_notu} • Öne çıkan: {en_iyi_secim} (%{en_iyi_guven}) • {spor_adi}"
    else:
        not_metni = f"Maç öncesi analiz • Öne çıkan: {en_iyi_secim} (%{en_iyi_guven}) • {spor_adi}"

    return en_iyi_secim, secenek_guvenleri, gemini_guven, claude_guven, not_metni

def api_istegi_at(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

BULTEN_VERISI = {
    "tarih": simdi_utc().astimezone(TR_TZ).strftime("%Y-%m-%d"),
    "secimler": [
        {
            "mac": "Barcelona - Chelsea (22:00)",
            "canli": True,
            "bitti": False,
            "dakika": "24'",
            "baslangic_saati": "22:00",
            "spor": "Futbol",
            "pazar": "Maç Sonucu",
            "tahmin": "MS 1",
            "oran": 1.62,
            "gemini_guven": 86,
            "claude_guven": 84,
            "not": "İlk yarı (24') canlı analizi • Öne çıkan: MS 1 (%85)",
            "secenek_guvenleri": {"MS 1": 85, "MS X": 74, "MS 2": 72},
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
            "gemini_guven": 80,
            "claude_guven": 80,
            "not": "Maç öncesi analiz • Öne çıkan: MS 1 (%80)",
            "secenek_guvenleri": {"MS 1": 80, "MS X": 72, "MS 2": 72},
            "oranlar": {"MS 1": 1.75, "MS X": 3.60, "MS 2": 4.40}
        }
    ]
}

def maclari_donustur(games, limit=15):
    sonuclar = []
    for g in (games or []):
        if len(sonuclar) >= limit:
            break
        home = g.get("home_team", "Ev")
        away = g.get("away_team", "Deplasman")
        spor_adi = g.get("sport_title") or g.get("sport_key") or "Spor"
        commence = g.get("commence_time", "")

        canli, bitti, dk_str, gecen_dk, saat_tr = mac_durumu_hesapla(commence)
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
            en_iyi_secim, secenek_guvenleri, gemini_guven, claude_guven, not_metni = mac_analizi_olustur(
                home, away, oranlar, canli, gecen_dk, dk_str, spor_adi
            )
            mac_etiketi = f"{home} - {away}" + (f" ({saat_tr})" if saat_tr else "")
            sonuclar.append({
                "mac": mac_etiketi,
                "canli": canli,
                "bitti": False,
                "dakika": dk_str,
                "baslangic_saati": saat_tr,
                "spor": spor_adi,
                "pazar": "Maç Sonucu",
                "tahmin": en_iyi_secim,
                "oran": oranlar[en_iyi_secim],
                "gemini_guven": gemini_guven,
                "claude_guven": claude_guven,
                "not": not_metni,
                "secenek_guvenleri": secenek_guvenleri,
                "oranlar": oranlar
            })
    return sonuclar

def oranlari_cek():
    bugun = simdi_utc().astimezone(TR_TZ).strftime("%Y-%m-%d")
    if not ODDS_API_KEY:
        print("UYARI: ODDS_API_KEY bos, yedek veri kullaniliyor.")
        return {**BULTEN_VERISI, "tarih": bugun}

    toplanan = []
    gorulen_maclar = set()

    kaynaklar = [
        f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h",
        f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    ]

    for url in kaynaklar:
        try:
            games = api_istegi_at(url)
            for item in maclari_donustur(games, limit=15):
                anahtar = item["mac"].lower()
                if anahtar not in gorulen_maclar:
                    gorulen_maclar.add(anahtar)
                    toplanan.append(item)
        except Exception as e:
            print("Kaynak uyarisi:", e)

    canli_sayisi = sum(1 for x in toplanan if x.get("canli"))
    baslamayan_sayisi = sum(1 for x in toplanan if not x.get("canli"))
    print(f"Toplam: {len(toplanan)} | Canli: {canli_sayisi} | Baslamayan: {baslamayan_sayisi}")

    if not toplanan:
        return {**BULTEN_VERISI, "tarih": bugun}

    return {"tarih": bugun, "secimler": toplanan[:25]}

def firebase_yaz(veri):
    hedef = f"{FIREBASE_DB_URL}/bulten.json"
    govde = json.dumps(veri).encode("utf-8")
    req = urllib.request.Request(hedef, data=govde, method="PUT", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status

if __name__ == "__main__":
    durum = firebase_yaz(oranlari_cek())
    print("Firebase guncellendi, durum:", durum)
