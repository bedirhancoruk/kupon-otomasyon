import os
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").rstrip("/")
TR_TZ = timezone(timedelta(hours=3))

MAX_CANLI_SURE_DK = 240
MAX_SECIM_SAYISI = 40

NON_FOOTBALL_KEYWORDS = [
    "basketball", "nba", "euroleague", "eurocup", "ncaa", "wnba", "basketbol",
    "tennis", "hockey", "nhl", "baseball", "mlb", "mma", "ufc", "boxing",
    "cricket", "rugby", "golf", "volleyball", "handball", "esports", "nfl", "americanfootball"
]

IMPORTANT_KEYWORDS = [
    ("galatasaray", 45), ("fenerbahce", 45), ("fenerbahçe", 45),
    ("besiktas", 42), ("beşiktaş", 42), ("trabzonspor", 38),
    ("real madrid", 45), ("barcelona", 45), ("atletico madrid", 38), ("atlético madrid", 38),
    ("manchester city", 44), ("manchester united", 40), ("arsenal", 42),
    ("liverpool", 43), ("chelsea", 40), ("tottenham", 37),
    ("bayern munich", 44), ("bayern münih", 44), ("borussia dortmund", 39), ("bayer leverkusen", 37),
    ("inter", 41), ("ac milan", 40), ("milan", 40), ("juventus", 40), ("napoli", 38),
    ("paris saint-germain", 41), ("psg", 41), ("benfica", 35), ("porto", 35), ("ajax", 35),
    ("champions league", 35), ("europa league", 28), ("conference league", 20),
    ("super lig", 28), ("süper lig", 28), ("premier league", 32), ("la liga", 30),
    ("bundesliga", 28), ("serie a", 28), ("ligue 1", 25), ("world cup", 45), ("euro", 38)
]

def simdi_tr():
    return datetime.now(TR_TZ)

def simdi_utc():
    return datetime.now(timezone.utc)

def futbol_mu(spor_key="", spor_adi="", mac_adi=""):
    metin = f"{spor_key} {spor_adi} {mac_adi}".lower()
    if any(k in metin for k in NON_FOOTBALL_KEYWORDS):
        return False
    return "soccer" in str(spor_key).lower() or "football" in metin or "futbol" in metin

def onem_puani_hesapla(home, away, spor_adi, spor_key, oranlar):
    metin = f"{home} {away} {spor_adi} {spor_key}".lower()
    puan = 10
    for anahtar, deger in IMPORTANT_KEYWORDS:
        if anahtar in metin:
            puan += deger
    if oranlar:
        en_dusuk = min(float(v) for v in oranlar.values() if float(v) > 1.0)
        if en_dusuk <= 1.80:
            puan += 6
    return puan

def parse_iso_utc(dt_str):
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
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

def basliktan_saat_cek(mac_adi):
    if not mac_adi:
        return ""
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", str(mac_adi))
    if not m:
        return ""
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"

def saat_tr_gecmis_mi(saat_str):
    if not saat_str:
        return False, "", 0
    try:
        hh, mm = map(int, saat_str.split(":"))
        now_tr = simdi_tr()
        baslangic_tr = now_tr.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now_tr.hour < 6 and hh >= 18:
            baslangic_tr = baslangic_tr - timedelta(days=1)
        fark_sn = (now_tr - baslangic_tr).total_seconds()
        if fark_sn >= 0:
            return True, f"{hh:02d}:{mm:02d}", int(fark_sn // 60)
        return False, f"{hh:02d}:{mm:02d}", 0
    except Exception:
        return False, "", 0

def mac_durumu_hesapla(commence_time_str, mac_adi=""):
    baslangic = parse_iso_utc(commence_time_str)
    if baslangic:
        baslangic_tr = baslangic.astimezone(TR_TZ)
        saat_tr = baslangic_tr.strftime("%H:%M")
        gecen_sn = (simdi_utc() - baslangic).total_seconds()
        if gecen_sn >= 0:
            gecen_dk = int(gecen_sn // 60)
            if gecen_dk > MAX_CANLI_SURE_DK:
                return False, True, "", gecen_dk, saat_tr
            return True, False, dakika_etiketi_uret(gecen_dk), gecen_dk, saat_tr

    etiket_saat = basliktan_saat_cek(mac_adi)
    gecmis, saat_tr, gecen_dk = saat_tr_gecmis_mi(etiket_saat)
    if gecmis:
        if gecen_dk > MAX_CANLI_SURE_DK:
            return False, True, "", gecen_dk, saat_tr
        return True, False, dakika_etiketi_uret(gecen_dk), gecen_dk, saat_tr

    return False, False, "", 0, saat_tr

def orana_gore_guven(oran, canli, gecen_dk):
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

def mac_analizi_olustur(oranlar, canli, gecen_dk, dk_str, spor_adi, onem_puani):
    secenek_guvenleri = {}
    for secim, oran_degeri in oranlar.items():
        secenek_guvenleri[secim] = orana_gore_guven(oran_degeri, canli, gecen_dk)

    aday_havuzu = secenek_guvenleri
    if canli:
        canli_uygun = {k: v for k, v in secenek_guvenleri.items() if float(oranlar.get(k, 0)) >= 1.50}
        if canli_uygun:
            aday_havuzu = canli_uygun

    en_iyi_secim = max(aday_havuzu.items(), key=lambda x: x[1])[0]
    en_iyi_guven = secenek_guvenleri[en_iyi_secim]

    gemini_guven = max(70, min(94, en_iyi_guven + (1 if canli and gecen_dk <= 60 else 0)))
    claude_guven = max(70, min(93, en_iyi_guven - (1 if canli and gecen_dk > 75 else 0)))
    onem_etiketi = "Önemli Maç" if onem_puani >= 35 else "Bülten Maçı"

    if canli:
        not_metni = f"Canlı ({dk_str}) • {onem_etiketi} • 1.50+ oran takibi • {spor_adi}"
    else:
        not_metni = f"Başlamamış • {onem_etiketi} • Öne çıkan: {en_iyi_secim} (%{en_iyi_guven}) • {spor_adi}"

    return en_iyi_secim, secenek_guvenleri, gemini_guven, claude_guven, not_metni

def api_istegi_at(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))

BULTEN_VERISI = {
    "tarih": simdi_tr().strftime("%Y-%m-%d"),
    "secimler": []
}

def maclari_donustur(games, limit=50):
    sonuclar = []
    for g in (games or []):
        if len(sonuclar) >= limit:
            break
        home = g.get("home_team", "Ev")
        away = g.get("away_team", "Deplasman")
        spor_key = g.get("sport_key") or "soccer"
        spor_adi = g.get("sport_title") or "Futbol"
        commence = g.get("commence_time", "")

        if not futbol_mu(spor_key, spor_adi, f"{home} - {away}"):
            continue

        on_etiket = f"{home} - {away}"
        canli, bitti, dk_str, gecen_dk, saat_tr = mac_durumu_hesapla(commence, on_etiket)
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
            onem_puani = onem_puani_hesapla(home, away, spor_adi, spor_key, oranlar)
            en_iyi_secim, secenek_guvenleri, gemini_guven, claude_guven, not_metni = mac_analizi_olustur(
                oranlar, canli, gecen_dk, dk_str, spor_adi, onem_puani
            )
            mac_etiketi = f"{home} - {away}" + (f" ({saat_tr})" if saat_tr else "")
            sonuclar.append({
                "mac": mac_etiketi,
                "canli": canli,
                "bitti": False,
                "dakika": dk_str,
                "baslangic_saati": saat_tr,
                "spor": "Futbol",
                "lig": spor_adi,
                "onem_puani": onem_puani,
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
    bugun = simdi_tr().strftime("%Y-%m-%d")
    if not ODDS_API_KEY:
        print("UYARI: ODDS_API_KEY bos, yedek veri kullaniliyor.")
        return {**BULTEN_VERISI, "tarih": bugun}

    baslamayan_liste = []
    canli_liste = []
    gorulen_maclar = set()

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    try:
        games = api_istegi_at(url)
        for item in maclari_donustur(games, limit=80):
            anahtar = item["mac"].lower()
            if anahtar in gorulen_maclar:
                continue
            gorulen_maclar.add(anahtar)
            if item.get("canli"):
                canli_liste.append(item)
            else:
                baslamayan_liste.append(item)
    except Exception as e:
        print("Futbol kaynagi uyarisi:", e)

    canli_liste.sort(key=lambda x: x.get("onem_puani", 0), reverse=True)
    baslamayan_liste.sort(key=lambda x: x.get("onem_puani", 0), reverse=True)

    birlesik = (canli_liste[:15] + baslamayan_liste[:25])[:MAX_SECIM_SAYISI]
    print(f"Futbol Toplam: {len(birlesik)} | Canli: {len(canli_liste[:15])} | Baslamayan: {len(baslamayan_liste[:25])}")

    if not birlesik:
        return {**BULTEN_VERISI, "tarih": bugun}

    return {"tarih": bugun, "secimler": birlesik}

def firebase_yaz(veri):
    hedef = f"{FIREBASE_DB_URL}/bulten.json"
    govde = json.dumps(veri).encode("utf-8")
    req = urllib.request.Request(hedef, data=govde, method="PUT", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status

if __name__ == "__main__":
    durum = firebase_yaz(oranlari_cek())
    print("Firebase guncellendi, durum:", durum)
