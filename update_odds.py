import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL", "https://kupon-bulten-default-rtdb.firebaseio.com").strip()
TR_TZ = timezone(timedelta(hours=3))

MAX_CANLI_SURE_DK = 240
MAX_SECIM_SAYISI = 40

NON_FOOTBALL_KEYWORDS = [
    "basketball", "nba", "euroleague", "eurocup", "ncaa", "wnba", "basketbol",
    "tennis", "hockey", "nhl", "baseball", "mlb", "mma", "ufc", "boxing",
    "cricket", "rugby", "golf", "volleyball", "handball", "esports", "nfl", "americanfootball"
]

TOP5_AND_SUPERLIG_KEYWORDS = [
    "super lig", "süper lig", "galatasaray", "fenerbahce", "fenerbahçe",
    "besiktas", "beşiktaş", "trabzonspor", "basaksehir", "başakşehir",
    "konyaspor", "antalyaspor", "alanyaspor", "sivasspor", "kayserispor",
    "kasimpasa", "kasımpaşa", "rizespor", "çaykur rizespor", "gaziantep", "hatayspor",
    "samsunspor", "goztepe", "göztepe", "eyupspor", "eyüpspor", "bodrum",
    "premier league", "epl", "manchester city", "manchester united", "arsenal",
    "liverpool", "chelsea", "tottenham", "aston villa", "newcastle", "brighton",
    "west ham", "everton", "fulham", "wolves", "wolverhampton", "brentford",
    "crystal palace", "nottingham forest", "bournemouth", "leicester", "ipswich", "southampton",
    "la liga", "real madrid", "barcelona", "atletico madrid", "atlético madrid",
    "athletic bilbao", "real sociedad", "real betis", "villarreal", "sevilla",
    "valencia", "celta vigo", "girona", "osasuna", "mallorca", "getafe", "las palmas", "alaves", "alavés",
    "serie a", "inter", "ac milan", "milan", "juventus", "napoli",
    "roma", "as roma", "lazio", "atalanta", "fiorentina", "bologna",
    "torino", "udinese", "genoa", "monza", "cagliari", "empoli", "verona", "lecce", "como", "parma",
    "bundesliga", "bayern munich", "bayern münih", "borussia dortmund", "bayer leverkusen",
    "rb leipzig", "stuttgart", "eintracht frankfurt", "freiburg", "hoffenheim",
    "wolfsburg", "werder bremen", "borussia monchengladbach", "mönchengladbach", "augsburg", "mainz", "bochum", "union berlin", "heidenheim",
    "ligue 1", "paris saint-germain", "psg", "marseille", "monaco",
    "lyon", "lille", "nice", "lens", "rennes", "strasbourg", "toulouse", "montpellier", "nantes", "reims", "brest", "auxerre"
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

PAZAR_GRUPLARI = {
    "MS 1": "Maç Sonucu",
    "MS X": "Maç Sonucu",
    "MS 2": "Maç Sonucu",
    "ÇŞ 1-X": "Çifte Şans",
    "ÇŞ 1-2": "Çifte Şans",
    "ÇŞ X-2": "Çifte Şans",
    "1.5 Üst": "1.5 Alt/Üst",
    "2.5 Üst": "2.5 Alt/Üst",
    "KG Var": "Karşılıklı Gol",
    "İY/MS 1/1": "İY / MS",
    "İY/MS 2/2": "İY / MS",
    "H2 (-1.5)": "Handikaplı MS"
}

def simdi_tr():
    return datetime.now(TR_TZ)

def simdi_utc():
    return datetime.now(timezone.utc)

def futbol_mu(spor_key="", spor_adi="", mac_adi=""):
    metin = f"{spor_key} {spor_adi} {mac_adi}".lower()
    if any(k in metin for k in NON_FOOTBALL_KEYWORDS):
        return False
    return "soccer" in str(spor_key).lower() or "football" in metin or "futbol" in metin

def bes_buyuk_veya_super_lig_mu(mac_adi="", spor_adi="", spor_key=""):
    metin = f"{mac_adi} {spor_adi} {spor_key}".lower()
    return any(k in metin for k in TOP5_AND_SUPERLIG_KEYWORDS)

def onem_puani_hesapla(home, away, spor_adi, spor_key, oranlar):
    metin = f"{home} {away} {spor_adi} {spor_key}".lower()
    puan = 35 if bes_buyuk_veya_super_lig_mu(metin, spor_adi, spor_key) else 10
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

def mac_dakikasi_coz(dk_str, gecen_dk=0):
    if isinstance(gecen_dk, (int, float)) and gecen_dk > 0:
        if gecen_dk <= 45:
            return int(gecen_dk), False
        if gecen_dk <= 60:
            return 45, True
        return min(105, int(gecen_dk) - 15), False

    s = str(dk_str or "").strip()
    if not s or s.upper() == "İY":
        return 45, True
    plus_m = re.match(r"^(\d+)\+(\d+)'?$", s)
    if plus_m:
        return int(plus_m.group(1)) + int(plus_m.group(2)), False
    num_m = re.match(r"^(\d+)'?$", s)
    if num_m:
        return int(num_m.group(1)), False
    return 1, False

def dakika_faz_bilgisi(dk_str, gecen_dk=0):
    dk, devre_arasi = mac_dakikasi_coz(dk_str, gecen_dk)
    if devre_arasi:
        return {
            "dk": 45,
            "faz_adi": "Devre Arası",
            "canli_carpan": 1.01,
            "aksiyon": "İkinci yarı tempo ve gol/üst senaryoları öne çıkıyor"
        }
    if dk <= 15:
        return {
            "dk": dk,
            "faz_adi": "İlk 15 Dakika",
            "canli_carpan": 0.98,
            "aksiyon": "Erken tempo analizi; temkinli ve yüksek güvenli seçenekler izlenmeli"
        }
    if dk <= 35:
        return {
            "dk": dk,
            "faz_adi": "İlk Yarı Ortası",
            "canli_carpan": 1.01,
            "aksiyon": "Oyun kurgusu oturdu; favori ve gol pazarları güçleniyor"
        }
    if dk <= 45:
        return {
            "dk": dk,
            "faz_adi": "İlk Yarı Sonu",
            "canli_carpan": 1.02,
            "aksiyon": "Devre sonu baskısı; 1.5 Üst ve KG Var kırılma anında"
        }
    if dk <= 65:
        return {
            "dk": dk,
            "faz_adi": "İkinci Yarı Girişi",
            "canli_carpan": 1.03,
            "aksiyon": "Maç açılıyor; 2.5 Üst, KG Var ve öne çıkan taraf güveni canlı"
        }
    if dk <= 78:
        return {
            "dk": dk,
            "faz_adi": "Son Çeyrek Girişi",
            "canli_carpan": 0.99,
            "aksiyon": "Skor ve yorgunluk etkisi kritik; yüksek güvenli oranlar öncelikli"
        }
    return {
        "dk": dk,
        "faz_adi": "Son Dakikalar",
        "canli_carpan": 0.95,
        "aksiyon": "Final dakikaları; geç gol ve skor koruma riski yüksek"
    }

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

def tum_pazar_oranlari_turet(base_oranlar, canli=False, dk_str="", gecen_dk=0):
    oranlar = dict(base_oranlar)
    o1 = float(oranlar.get("MS 1", 2.30))
    ox = float(oranlar.get("MS X", 3.40))
    o2 = float(oranlar.get("MS 2", 2.80))

    if "ÇŞ 1-X" not in oranlar:
        oranlar["ÇŞ 1-X"] = round(max(1.30, 1.0 / (1.0 / max(1.05, o1) + 1.0 / max(1.05, ox)) * 0.92), 2)
    if "ÇŞ 1-2" not in oranlar:
        oranlar["ÇŞ 1-2"] = round(max(1.30, 1.0 / (1.0 / max(1.05, o1) + 1.0 / max(1.05, o2)) * 0.92), 2)
    if "ÇŞ X-2" not in oranlar:
        oranlar["ÇŞ X-2"] = round(max(1.30, 1.0 / (1.0 / max(1.05, ox) + 1.0 / max(1.05, o2)) * 0.92), 2)

    fav_odd = min(o1, o2)
    if "1.5 Üst" not in oranlar:
        oranlar["1.5 Üst"] = round(max(1.30, min(1.85, 1.24 + (fav_odd - 1.40) * 0.22)), 2)
    if "2.5 Üst" not in oranlar:
        oranlar["2.5 Üst"] = round(max(1.50, min(2.45, 1.62 + (fav_odd - 1.50) * 0.30)), 2)
    if "KG Var" not in oranlar:
        oranlar["KG Var"] = round(max(1.50, min(2.35, 1.65 + abs(o1 - o2) * 0.18)), 2)
    if "İY/MS 1/1" not in oranlar and o1 <= 2.40:
        oranlar["İY/MS 1/1"] = round(max(1.65, o1 * 1.48), 2)
    if "İY/MS 2/2" not in oranlar and o2 <= 2.40:
        oranlar["İY/MS 2/2"] = round(max(1.65, o2 * 1.48), 2)
    if "H2 (-1.5)" not in oranlar and o2 <= 1.75:
        oranlar["H2 (-1.5)"] = round(max(1.55, o2 * 1.38), 2)

    if canli:
        dk, _ = mac_dakikasi_coz(dk_str, gecen_dk)
        for k, val in list(oranlar.items()):
            fval = float(val)
            if k in ("2.5 Üst", "KG Var") and 45 <= dk <= 75:
                oranlar[k] = round(max(1.50, fval * 0.97), 2)
            elif k in ("2.5 Üst", "KG Var") and dk > 75:
                oranlar[k] = round(min(3.20, fval * 1.06), 2)
            elif k.startswith("MS ") and dk >= 70:
                oranlar[k] = round(max(1.15, fval * (0.95 if fval < 2.1 else 1.05)), 2)

    return oranlar

def orana_gore_guven(secim, oran, canli, gecen_dk, dk_str, is_top5_super, onem_puani):
    try:
        o = float(oran)
    except Exception:
        o = 2.0

    if o <= 1.35:
        baz = 86
    elif o <= 1.55:
        baz = 83
    elif o <= 1.80:
        baz = 80
    elif o <= 2.15:
        baz = 77
    else:
        baz = 74

    pazar_etkisi = 0
    if secim in ("1.5 Üst", "ÇŞ 1-X", "ÇŞ 1-2", "ÇŞ X-2"):
        pazar_etkisi += 2
    elif secim in ("2.5 Üst", "KG Var"):
        pazar_etkisi += 1

    if is_top5_super:
        pazar_etkisi += 2
    if onem_puani >= 50:
        pazar_etkisi += 1

    if not canli:
        return max(72, min(92, baz + pazar_etkisi))

    faz = dakika_faz_bilgisi(dk_str, gecen_dk)
    dk = faz["dk"]
    dk_farki = 0

    if dk <= 15:
        dk_farki = -1 if secim in ("2.5 Üst", "KG Var", "İY/MS 1/1", "İY/MS 2/2") else 0
    elif dk <= 35:
        dk_farki = 1 if secim in ("MS 1", "MS 2", "ÇŞ 1-X", "ÇŞ 1-2", "ÇŞ X-2", "1.5 Üst") else 0
    elif dk <= 45:
        dk_farki = 2 if secim in ("1.5 Üst", "2.5 Üst", "KG Var") else 0
    elif dk <= 65:
        dk_farki = 2 if secim in ("2.5 Üst", "KG Var", "MS 1", "MS 2") else 1
    elif dk <= 78:
        dk_farki = 1 if (secim in ("2.5 Üst", "KG Var") or o <= 1.75) else -2
    else:
        dk_farki = -3 if secim in ("2.5 Üst", "KG Var") else -2

    skoru = (baz + pazar_etkisi + dk_farki) * faz["canli_carpan"]
    return max(71, min(93, int(round(skoru))))

def mac_analizi_olustur(oranlar, canli, gecen_dk, dk_str, spor_adi, onem_puani, is_top5_super):
    secenek_guvenleri = {}
    for secim, oran_degeri in oranlar.items():
        secenek_guvenleri[secim] = orana_gore_guven(
            secim, oran_degeri, canli, gecen_dk, dk_str, is_top5_super, onem_puani
        )

    aday_havuzu = {
        k: v for k, v in secenek_guvenleri.items()
        if (not canli or float(oranlar.get(k, 0)) >= 1.50)
    }
    if not aday_havuzu:
        aday_havuzu = secenek_guvenleri

    en_iyi_secim = max(aday_havuzu.items(), key=lambda x: (x[1], float(oranlar.get(x[0], 0))))[0]
    en_iyi_guven = secenek_guvenleri[en_iyi_secim]
    pazar_adi = PAZAR_GRUPLARI.get(en_iyi_secim, "Maç Sonucu")

    faz = dakika_faz_bilgisi(dk_str, gecen_dk)
    gemini_guven = max(72, min(94, en_iyi_guven + (1 if canli and faz["dk"] <= 65 else 0)))
    claude_guven = max(72, min(93, en_iyi_guven - (1 if canli and faz["dk"] > 75 else 0)))

    if canli and is_top5_super:
        not_metni = f"Canlı ({dk_str} • {faz['faz_adi']}) • 5 Büyük/Süper Lig: {en_iyi_secim} (%{en_iyi_guven}) • {faz['aksiyon']}"
    elif canli:
        not_metni = f"Canlı ({dk_str} • {faz['faz_adi']}) • {pazar_adi}: {en_iyi_secim} (%{en_iyi_guven}) • {faz['aksiyon']}"
    else:
        not_metni = f"Başlamamış • {pazar_adi}: {en_iyi_secim} (%{en_iyi_guven}) • {spor_adi}"

    return en_iyi_secim, pazar_adi, secenek_guvenleri, gemini_guven, claude_guven, not_metni

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

        baz_oranlar = {}
        for bm in g.get("bookmakers", [])[:1]:
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for oc in mkt.get("outcomes", []):
                        price = float(oc.get("price", 1.35))
                        if oc.get("name") == home:
                            baz_oranlar["MS 1"] = price
                        elif oc.get("name") == away:
                            baz_oranlar["MS 2"] = price
                        elif oc.get("name") == "Draw":
                            baz_oranlar["MS X"] = price

        if baz_oranlar:
            oranlar = tum_pazar_oranlari_turet(baz_oranlar, canli=canli, dk_str=dk_str, gecen_dk=gecen_dk)
            is_top5_super = bes_buyuk_veya_super_lig_mu(f"{home} - {away}", spor_adi, spor_key)
            onem_puani = onem_puani_hesapla(home, away, spor_adi, spor_key, oranlar)
            en_iyi_secim, pazar_adi, secenek_guvenleri, gemini_guven, claude_guven, not_metni = mac_analizi_olustur(
                oranlar, canli, gecen_dk, dk_str, spor_adi, onem_puani, is_top5_super
            )
            faz = dakika_faz_bilgisi(dk_str, gecen_dk)
            mac_etiketi = f"{home} - {away}" + (f" ({saat_tr})" if saat_tr else "")
            sonuclar.append({
                "mac": mac_etiketi,
                "canli": canli,
                "bitti": False,
                "dakika": dk_str,
                "dakika_fazi": faz["faz_adi"] if canli else "Maç Önü",
                "gecen_dakika": gecen_dk if canli else 0,
                "baslangic_saati": saat_tr,
                "spor": "Futbol",
                "lig": spor_adi,
                "top5_veya_super_lig": is_top5_super,
                "onem_puani": onem_puani,
                "pazar": pazar_adi,
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

def firebase_icin_temizle(deger):
    if isinstance(deger, dict):
        temiz_sozluk = {}
        for anahtar, icerik in deger.items():
            temiz_anahtar = re.sub(r"[.$#\[\]/]", "-", str(anahtar)).strip()
            if not temiz_anahtar:
                temiz_anahtar = "bos_anahtar"
            temiz_sozluk[temiz_anahtar] = firebase_icin_temizle(icerik)
        return temiz_sozluk
    if isinstance(deger, list):
        return [firebase_icin_temizle(eleman) for eleman in deger]
    return deger

def firebase_yaz(veri):
    base = FIREBASE_DB_URL.rstrip("/")
    if base.endswith("/bulten.json"):
        hedef = base
    elif base.endswith("/bulten"):
        hedef = f"{base}.json"
    else:
        hedef = f"{base}/bulten.json"

    temiz_veri = firebase_icin_temizle(veri)
    govde = json.dumps(temiz_veri, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        hedef,
        data=govde,
        method="PUT",
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        detay = e.read().decode("utf-8", errors="replace")
        print(f"Firebase HTTP {e.code} hatasi -> Hedef: {hedef} | Detay: {detay}")
        raise

if __name__ == "__main__":
    durum = firebase_yaz(oranlari_cek())
    print("Firebase guncellendi, durum:", durum)
