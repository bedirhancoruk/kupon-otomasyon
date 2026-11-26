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
MAX_SECIM_SAYISI = 80
MIN_OLASILIK_ESIGI = 58
MIN_RAKIP_FARKI = 8

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
    "2.5 Üst": "2.5 Alt/Üst",
    "2.5 Alt": "2.5 Alt/Üst"
}

KARSI_PAZARLAR = {
    "2.5 Üst": "2.5 Alt",
    "2.5 Alt": "2.5 Üst"
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

def otomatik_onem_puani(home, away, spor_adi, spor_key, oranlar, canli):
    metin = f"{home} {away} {spor_adi} {spor_key}".lower()
    puan = 35 if bes_buyuk_veya_super_lig_mu(metin, spor_adi, spor_key) else 20
    if canli:
        puan += 10
    for anahtar, deger in IMPORTANT_KEYWORDS:
        if anahtar in metin:
            puan += deger
    if oranlar:
        en_dusuk = min(float(v) for v in oranlar.values() if float(v) > 1.0)
        if en_dusuk <= 1.65:
            puan += 8
        elif en_dusuk <= 2.00:
            puan += 4
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
        return {"dk": 45, "faz_adi": "Devre Arası", "canli_carpan": 1.0, "aksiyon": "İkinci yarı başlangıcı ve taktik ayarlar"}
    if dk <= 15:
        return {"dk": dk, "faz_adi": "İlk 15 Dakika", "canli_carpan": 0.99, "aksiyon": "Erken tempo ve savunma yerleşimi"}
    if dk <= 35:
        return {"dk": dk, "faz_adi": "İlk Yarı Ortası", "canli_carpan": 1.0, "aksiyon": "Oyun kurgusu ve top hakimiyeti netleşiyor"}
    if dk <= 45:
        return {"dk": dk, "faz_adi": "İlk Yarı Sonu", "canli_carpan": 1.01, "aksiyon": "Devre sonu baskısı ve duran top ihtimali"}
    if dk <= 65:
        return {"dk": dk, "faz_adi": "İkinci Yarı Girişi", "canli_carpan": 1.01, "aksiyon": "Maç açılıyor ve boşluklar artıyor"}
    if dk <= 78:
        return {"dk": dk, "faz_adi": "Son Çeyrek Girişi", "canli_carpan": 0.99, "aksiyon": "Yorgunluk ve değişikliklerle kırılma anı"}
    return {"dk": dk, "faz_adi": "Son Dakikalar", "canli_carpan": 0.98, "aksiyon": "Final dakikaları ve risk/tempo dengesi"}

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

def cifte_sans_hesapla(oa, ob, tekli_oran):
    try:
        a = max(1.05, float(oa))
        b = max(1.05, float(ob))
        t = float(tekli_oran) if tekli_oran and float(tekli_oran) > 1.0 else 9.99
        ham = 1.0 / ((1.0 / a) + (1.0 / b)) * 0.95
        return round(max(1.05, min(t - 0.05, ham)), 2)
    except Exception:
        return 1.30

def gercek_oranlari_hazirla(api_oranlar):
    oranlar = {}
    for k, v in (api_oranlar or {}).items():
        try:
            fv = round(float(v), 2)
            if fv > 1.0:
                oranlar[k] = fv
        except Exception:
            continue

    o1 = oranlar.get("MS 1")
    ox = oranlar.get("MS X")
    o2 = oranlar.get("MS 2")

    if o1 and ox and "ÇŞ 1-X" not in oranlar:
        oranlar["ÇŞ 1-X"] = cifte_sans_hesapla(o1, ox, o1)
    if o1 and o2 and "ÇŞ 1-2" not in oranlar:
        oranlar["ÇŞ 1-2"] = cifte_sans_hesapla(o1, o2, min(o1, o2))
    if ox and o2 and "ÇŞ X-2" not in oranlar:
        oranlar["ÇŞ X-2"] = cifte_sans_hesapla(ox, o2, o2)

    return oranlar

def canli_dakikada_uygun_mu(secim, dk, devre_arasi):
    if devre_arasi:
        return True
    if dk <= 15 and secim == "2.5 Üst":
        return False
    if dk >= 78 and secim == "2.5 Üst":
        return False
    return True

def secenek_olasiligi_hesapla(secim, oran, canli, gecen_dk, dk_str, is_top5_super, onem_puani):
    try:
        o = max(1.05, float(oran))
    except Exception:
        o = 1.80

    implied = (1.0 / o) * 100.0 * 1.06
    if secim.startswith("ÇŞ "):
        implied += 4.0
    if is_top5_super:
        implied += 2.0
    if onem_puani >= 50:
        implied += 1.5

    if canli:
        faz = dakika_faz_bilgisi(dk_str, gecen_dk)
        dk = faz["dk"]
        if dk <= 15 and secim == "2.5 Üst":
            implied -= 8.0
        elif 20 <= dk <= 65:
            implied += 2.5
        elif dk >= 78:
            implied -= 5.0
        implied *= faz["canli_carpan"]

    return max(45, min(92, int(round(implied))))

def detayli_analiz_paketi_olustur(mac_adi, spor_adi, en_iyi_secim, oran_degeri, olasilik, ham_olasiliklar, canli, dk_str, faz, is_top5_super):
    elenen_isimler = [k for k in ham_olasiliklar if k != en_iyi_secim and ham_olasiliklar[k] < olasilik]
    rakip = KARSI_PAZARLAR.get(en_iyi_secim)
    if rakip and rakip in ham_olasiliklar:
        fark = olasilik - ham_olasiliklar[rakip]
        eleme_gerekcesi = f"{rakip} (% {ham_olasiliklar[rakip]}) ile aradaki {fark} puanlık olasılık farkı ve eşik filtresi nedeniyle elendi."
    elif elenen_isimler:
        eleme_gerekcesi = f"Zayıf/düşük olasılıklı seçenekler ({', '.join(elenen_isimler[:3])}) olasılık filtresinde elendi."
    else:
        eleme_gerekcesi = "Diğer alternatifler piyasa olasılığı ve güven eşiğinin gerisinde kaldığı için elendi."

    lig_notu = "5 Büyük Lig veya Süper Lig profili veri kalitesini artırıyor." if is_top5_super else f"{spor_adi} ligi oran yapısı baz alındı."
    if canli:
        tempo_notu = f"{dk_str} ({faz['faz_adi']}): {faz['aksiyon']}. {lig_notu}"
        risk_notu = f"Canlı tempo ve skor değişimi olasılığı etkileyebilir; {oran_degeri:.2f} oran disipliniyle kademeli değerlendirilmeli."
    else:
        tempo_notu = f"Maç öncesi analiz ({spor_adi}): {faz['aksiyon']}. {lig_notu}"
        risk_notu = f"Maç önü {oran_degeri:.2f} oran seviyesi olasılık eşiğine uygun; kadro/eksik haberleri maç saatine yakın kontrol edilmeli."

    secim_notu = f"{en_iyi_secim} seçeneği %{olasilik} AI olasılık skoru ve {oran_degeri:.2f} oran ile öne çıktı. {eleme_gerekcesi}"
    ozet_not = f"{en_iyi_secim} (%{olasilik} • {oran_degeri:.2f}) | {eleme_gerekcesi}"

    return ozet_not, {
        "yon": en_iyi_secim,
        "olasilik": olasilik,
        "oran": round(float(oran_degeri), 2),
        "neden_secildi_ve_elendi": secim_notu,
        "tempo_senaryosu": tempo_notu,
        "risk_ve_kupon_notu": risk_notu
    }

def mac_analizi_olustur(mac_adi, oranlar, canli, gecen_dk, dk_str, spor_adi, onem_puani, is_top5_super):
    faz = dakika_faz_bilgisi(dk_str, gecen_dk)
    dk = faz["dk"]
    _, devre_arasi = mac_dakikasi_coz(dk_str, gecen_dk)

    ham_olasiliklar = {}
    for secim, oran_degeri in oranlar.items():
        if canli and not canli_dakikada_uygun_mu(secim, dk, devre_arasi):
            continue
        ham_olasiliklar[secim] = secenek_olasiligi_hesapla(
            secim, oran_degeri, canli, gecen_dk, dk_str, is_top5_super, onem_puani
        )

    elenmis_olasiliklar = {}
    for secim, ol in ham_olasiliklar.items():
        if ol < MIN_OLASILIK_ESIGI:
            continue
        rakip = KARSI_PAZARLAR.get(secim)
        if rakip and rakip in ham_olasiliklar:
            if (ol - ham_olasiliklar[rakip]) < MIN_RAKIP_FARKI:
                continue
        elenmis_olasiliklar[secim] = ol

    aday_havuzu = {
        k: v for k, v in elenmis_olasiliklar.items()
        if (not canli or float(oranlar.get(k, 0)) >= 1.50)
    }

    if not aday_havuzu and elenmis_olasiliklar:
        aday_havuzu = elenmis_olasiliklar

    if not aday_havuzu:
        en_iyi_secim = max(ham_olasiliklar.items(), key=lambda x: x[1])[0]
        en_iyi_olasilik = ham_olasiliklar[en_iyi_secim]
        elenmis_olasiliklar = {en_iyi_secim: en_iyi_olasilik}
    else:
        en_iyi_secim = max(aday_havuzu.items(), key=lambda x: (x[1], float(oranlar.get(x[0], 0))))[0]
        en_iyi_olasilik = elenmis_olasiliklar[en_iyi_secim]

    filtreli_oranlar = {k: oranlar[k] for k in elenmis_olasiliklar if k in oranlar}
    pazar_adi = PAZAR_GRUPLARI.get(en_iyi_secim, "Maç Sonucu")
    secilen_oran = filtreli_oranlar.get(en_iyi_secim, oranlar[en_iyi_secim])

    gemini_guven = max(80, min(92, en_iyi_olasilik + (1 if canli and dk <= 65 else 0)))
    claude_guven = max(80, min(92, en_iyi_olasilik - (1 if canli and dk > 75 else 0)))

    not_metni, analiz_detay = detayli_analiz_paketi_olustur(
        mac_adi, spor_adi, en_iyi_secim, secilen_oran, en_iyi_olasilik,
        ham_olasiliklar, canli, dk_str, faz, is_top5_super
    )

    return en_iyi_secim, pazar_adi, elenmis_olasiliklar, filtreli_oranlar, gemini_guven, claude_guven, not_metni, analiz_detay

def api_istegi_at(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))

BULTEN_VERISI = {
    "tarih": simdi_tr().strftime("%Y-%m-%d"),
    "secimler": []
}

def maclari_donustur(games, limit=120):
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

        api_oranlar = {}
        for bm in g.get("bookmakers", [])[:1]:
            for mkt in bm.get("markets", []):
                mkt_key = mkt.get("key")
                if mkt_key == "h2h":
                    for oc in mkt.get("outcomes", []):
                        price = float(oc.get("price", 0))
                        if price > 1.0:
                            if oc.get("name") == home:
                                api_oranlar["MS 1"] = price
                            elif oc.get("name") == away:
                                api_oranlar["MS 2"] = price
                            elif oc.get("name") == "Draw":
                                api_oranlar["MS X"] = price
                elif mkt_key == "totals":
                    for oc in mkt.get("outcomes", []):
                        price = float(oc.get("price", 0))
                        if price > 1.0 and float(oc.get("point", 0)) == 2.5:
                            if oc.get("name") == "Over":
                                api_oranlar["2.5 Üst"] = price
                            elif oc.get("name") == "Under":
                                api_oranlar["2.5 Alt"] = price

        oranlar = gercek_oranlari_hazirla(api_oranlar)
        if not oranlar:
            continue

        is_top5_super = bes_buyuk_veya_super_lig_mu(f"{home} - {away}", spor_adi, spor_key)
        onem_puani = otomatik_onem_puani(home, away, spor_adi, spor_key, oranlar, canli)
        faz = dakika_faz_bilgisi(dk_str, gecen_dk)
        mac_etiketi = f"{home} - {away}" + (f" ({saat_tr})" if saat_tr else "")

        en_iyi_secim, pazar_adi, secenek_guvenleri, filtreli_oranlar, gemini_guven, claude_guven, not_metni, analiz_detay = mac_analizi_olustur(
            mac_etiketi, oranlar, canli, gecen_dk, dk_str, spor_adi, onem_puani, is_top5_super
        )

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
            "oran": filtreli_oranlar.get(en_iyi_secim, oranlar[en_iyi_secim]),
            "gemini_guven": gemini_guven,
            "claude_guven": claude_guven,
            "not": not_metni,
            "analiz_detay": analiz_detay,
            "secenek_guvenleri": secenek_guvenleri,
            "oranlar": filtreli_oranlar if filtreli_oranlar else oranlar
        })
    return sonuclar

def oranlari_cek():
    bugun = simdi_tr().strftime("%Y-%m-%d")
    if not ODDS_API_KEY:
        print("UYARI: ODDS_API_KEY bos.")
        return {**BULTEN_VERISI, "tarih": bugun}

    baslamayan_liste = []
    canli_liste = []
    gorulen_maclar = set()

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h,totals"
    try:
        games = api_istegi_at(url)
        for item in maclari_donustur(games, limit=120):
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

    birlesik = (canli_liste[:30] + baslamayan_liste[:50])[:MAX_SECIM_SAYISI]
    print(f"Futbol Toplam: {len(birlesik)} | Canli: {len(canli_liste[:30])} | Baslamayan: {len(baslamayan_liste[:50])}")

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
