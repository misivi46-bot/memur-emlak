import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim
from datetime import datetime
import json
from google.oauth2 import service_account
from google.cloud import firestore
from PIL import Image
import io

# --- 1. SAYFA AYARLARI VE MOBİL DESTEK (PWA) ---
st.set_page_config(page_title="Memur Emlak & Tayin Portalı", layout="wide", page_icon="🏢")

st.markdown('<link rel="manifest" href="/manifest.json">', unsafe_allow_html=True)
st.markdown('<meta name="apple-mobile-web-app-capable" content="yes">', unsafe_allow_html=True)

st.markdown("""
    <style>
        iframe { max-width: 100% !important; overflow: hidden !important; border-radius: 12px; }
        .main { background-color: #f8f9fa; }
        /* Yatay menüyü sekmelere benzetmek için ufak bir CSS */
        div[role="radiogroup"] { flex-direction: row; gap: 15px; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FIREBASE BAĞLANTISI ---
@st.cache_resource
def get_db():
    try:
        key_dict = json.loads(st.secrets["firebase_key"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds)
    except Exception as e:
        st.error("Veritabanı bağlantı hatası. Secrets ayarlarını kontrol edin.")
        return None

db = get_db()

# --- 3. VERİ YÜKLEME ---
def load_data():
    if db is None: return
    st.session_state.users = {doc.id: doc.to_dict() for doc in db.collection('users').stream()}
    
    if "misivi46" not in st.session_state.users:
        admin_data = {"sifre": "Elvinmelek46**", "rol": "yonetici", "ad": "Sinan", "favorites": []}
        db.collection('users').document("misivi46").set(admin_data)
        st.session_state.users["misivi46"] = admin_data

    st.session_state.houses = [doc.to_dict() for doc in db.collection('houses').stream()]
    st.session_state.messages = [doc.to_dict() for doc in db.collection('messages').stream()]

if 'data_loaded' not in st.session_state:
    st.session_state.users, st.session_state.houses, st.session_state.messages = {}, [], []
    load_data()
    st.session_state.data_loaded = True

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_role = None

# --- 4. YARDIMCI FONKSİYONLAR ---
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "ırk", "defol", "lan"]

def icerik_uygun_mu(metin):
    return not any(kelime in metin.lower() for kelime in YASAKLI_KELIMELER)

def koordinati_adrese_cevir(lat, lon):
    try:
        loc = Nominatim(user_agent="memur_emlak_v6").reverse(f"{lat}, {lon}", timeout=3)
        return loc.address if loc else "Adres bulunamadı."
    except: return "Adres servisi meşgul."

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 2)

# YENİ: ŞEHİR VE KURUM VERİTABANI
CITIES = {
    "Elazığ": {
        "center": [38.6748, 39.2225],
        "institutions": [
            {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
            {"name": "Fethi Sekin Şehir Hastanesi", "lat": 38.6738, "lon": 39.1963},
            {"name": "Adliye", "lat": 38.6705, "lon": 39.2215},
            {"name": "Fırat Üniversitesi", "lat": 38.6756, "lon": 39.1970},
            {"name": "İl Emniyet Müdürlüğü", "lat": 38.6710, "lon": 39.1840}
        ]
    },
    "Konya": {
        "center": [37.8746, 32.4931],
        "institutions": [
            {"name": "Konya Valiliği", "lat": 37.8715, "lon": 32.4846},
            {"name": "Şehir Hastanesi", "lat": 37.8580, "lon": 32.5350},
            {"name": "Konya Adliyesi", "lat": 37.8785, "lon": 32.5280},
            {"name": "Selçuk Üniversitesi", "lat": 38.0260, "lon": 32.5125},
            {"name": "İl Emniyet Müdürlüğü", "lat": 37.8860, "lon": 32.4900}
        ]
    },
    "Ankara": {
        "center": [39.9334, 32.8597],
        "institutions": [
            {"name": "Ankara Valiliği", "lat": 39.9410, "lon": 32.8545},
            {"name": "Bilkent Şehir Hastanesi", "lat": 39.8955, "lon": 32.7620},
            {"name": "Ankara Adliyesi", "lat": 39.9300, "lon": 32.8500},
            {"name": "ODTÜ", "lat": 39.8914, "lon": 32.7846},
            {"name": "Emniyet Genel Müd.", "lat": 39.9145, "lon": 32.8505}
        ]
    }
}

# --- 5. SIDEBAR (AUTH, ŞEHİR & FİLTRE) ---
with st.sidebar:
    st.title("🏡 İşlemler")
    
    # YENİ: ŞEHİR SEÇİMİ
    secilen_sehir = st.selectbox("🏙️ Şehir Seçin:", list(CITIES.keys()))
    aktif_merkez = CITIES[secilen_sehir]["center"]
    aktif_kurumlar = CITIES[secilen_sehir]["institutions"]

    max_fiyat, kurum_sec, max_mesafe = 50000, "Farketmez", 50.0
    oda_sec, esya_sec = "Farketmez", "Farketmez"

    if not st.session_state.logged_in:
        auth = st.radio("Seçim:", ["Giriş Yap", "Üye Ol"])
        if auth == "Giriş Yap":
            with st.form("l_f"):
                u, p = st.text_input("Kullanıcı Adı"), st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş"):
                    load_data()
                    if u in st.session_state.users and st.session_state.users[u]["sifre"] == p:
                        st.session_state.logged_in, st.session_state.current_user, st.session_state.user_role = True, u, st.session_state.users[u]["rol"]
                        st.rerun()
                    else: st.error("Hatalı giriş!")
        else:
            with st.form("s_f"):
                n_a, n_u, n_p = st.text_input("Ad Soyad"), st.text_input("Kullanıcı Adı"), st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt Ol"):
                    if n_a and n_u and n_p:
                        if n_u in st.session_state.users: st.error("Kullanıcı adı alınmış.")
                        else:
                            u_data = {"sifre": n_p, "rol": "kullanici", "ad": n_a, "favorites": []}
                            db.collection('users').document(n_u).set(u_data)
                            st.success("Kayıt başarılı!")
    else:
        st.success(f"Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}")
        
        with st.expander("⚙️ Şifre İşlemleri"):
            if st.session_state.user_role == "yonetici":
                target = st.selectbox("Üye Seç:", list(st.session_state.users.keys()))
                new_p_admin = st.text_input("Yeni Şifre", type="password", key="admin_pw_input")
                if st.button("Şifreyi Güncelle", key="admin_pw_btn"):
                    if new_p_admin:
                        st.session_state.users[target]["sifre"] = new_p_admin
                        db.collection('users').document(target).update({"sifre": new_p_admin})
                        st.success(f"Güncellendi.")
            else:
                old_p, new_p = st.text_input("Eski Şifre", type="password"), st.text_input("Yeni Şifre", type="password")
                if st.button("Şifremi Kaydet"):
                    if old_p == st.session_state.users[st.session_state.current_user]["sifre"] and new_p:
                        st.session_state.users[st.session_state.current_user]["sifre"] = new_p
                        db.collection('users').document(st.session_state.current_user).update({"sifre": new_p})
                        st.success("Güncellendi.")

        with st.expander("🔍 Detaylı Filtrele"):
            max_fiyat = st.slider("Maks. Bütçe", 0, 50000, 50000, step=500)
            oda_sec = st.selectbox("Oda", ["Farketmez", "1+0", "1+1", "2+1", "3+1", "4+1 ve üzeri"])
            esya_sec = st.radio("Eşya", ["Farketmez", "Eşyalı", "Boş"])
            kurum_sec = st.selectbox("Kuruma Yakınlık:", ["Farketmez"] + [i["name"] for i in aktif_kurumlar])
            if kurum_sec != "Farketmez": max_mesafe = st.slider("Mesafe (km)", 0.5, 30.0, 5.0)

        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()

# --- FİLTRELEME MANTIĞI ---
# 1. Aşama: Sadece seçilen şehre 100 km yakınlıktaki evleri al (Diğer şehirleri gizle)
f_houses = [h for h in st.session_state.houses if calculate_distance(h["lat"], h["lon"], aktif_merkez[0], aktif_merkez[1]) <= 100]

# 2. Aşama: Kullanıcı filtrelerini uygula
f_houses = [h for h in f_houses if h["price"] <= max_fiyat]
if oda_sec != "Farketmez": f_houses = [h for h in f_houses if h.get("rooms", "Belirtilmemiş") == oda_sec]
if esya_sec != "Farketmez":
    esya_bool = True if esya_sec == "Eşyalı" else False
    f_houses = [h for h in f_houses if h.get("furnished", False) == esya_bool]
if kurum_sec != "Farketmez":
    inst = next(i for i in aktif_kurumlar if i["name"] == kurum_sec)
    f_houses = [h for h in f_houses if calculate_distance(h["lat"], h["lon"], inst["lat"], inst["lon"]) <= max_mesafe]

# --- 6. ANA PANEL (YÖNLENDİREBİLİR YATAY MENÜ) ---
tab_names = ["📍 Harita", "🏠 İlan Ekle", "📋 Tüm İlanlar", "⭐ Favoriler", "📩 Mesajlar"]
if st.session_state.user_role == "yonetici": tab_names.append("📊 Admin")

# Otomatik yönlendirme için aktif sekmeyi session_state'de tutuyoruz
if "active_tab" not in st.session_state:
    st.session_state.active_tab = tab_names[0]

# Sekme görünümünde radyo butonları
aktif_sekme = st.radio("Menü", tab_names, horizontal=True, label_visibility="collapsed", key="active_tab")

if aktif_sekme == "📍 Harita":
    m = folium.Map(location=aktif_merkez, zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    for i in aktif_kurumlar: folium.Marker([i["lat"], i["lon"]], popup=i["name"], icon=folium.Icon(color="blue", icon="briefcase", prefix='fa')).add_to(m)
    
    if st.session_state.logged_in:
        marker_cluster = MarkerCluster().add_to(m)
        for h in f_houses:
            dist_items = "".join([f"<li style='margin-bottom:2px;'><b>{i['name']}:</b> {calculate_distance(h['lat'], h['lon'], i['lat'], i['lon'])} km</li>" for i in aktif_kurumlar])
            img_b64 = h.get("image", "")
            img_tag = f'<img src="data:image/jpeg;base64,{img_b64}" style="width:100%; border-radius:8px; margin-bottom:8px;">' if img_b64 else ""
            nav_link = f"https://www.google.com/maps/dir/?api=1&destination={h['lat']},{h['lon']}"
            
            popup_html = f"""
            <div style='width:240px; font-family: sans-serif;'>
                {img_tag}
                <b style='font-size:14px;'>{h['title']}</b><br>
                <span style='color:#27ae60; font-size:16px; font-weight:bold;'>{h['price']} TL</span><br>
                <hr style='margin:8px 0;'>
                <a href="{nav_link}" target="_blank" style="display:block; text-align:center; background:#4285F4; color:white; text-decoration:none; padding:5px; border-radius:5px; font-size:12px;">📍 Yol Tarifi Al</a>
                <p style='font-size:11px; margin:8px 0 4px 0;'><b>Kurumlara Uzaklık:</b></p>
                <div style='max-height: 90px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; padding: 4px; background-color: #fcfcfc;'>
                    <ul style='margin:0; padding-left:15px; font-size:11px;'>{dist_items}</ul>
                </div>
            </div>"""
            folium.Marker([h["lat"], h["lon"]], popup=folium.Popup(popup_html, max_width=260), icon=folium.Icon(color="green", icon="home")).add_to(marker_cluster)
    else: st.info("İlanları görmek için giriş yapın.")
    
    m_res = st_folium(m, use_container_width=True, height=550, returned_objects=["last_clicked"])
    
    # YENİ: TIKLAMA YAKALAYICI VE YÖNLENDİRİCİ
    if m_res and m_res.get("last_clicked"):
        click_data = m_res["last_clicked"]
        if st.session_state.get("prev_click") != click_data:
            st.session_state.prev_click = click_data
            st.session_state.active_tab = "🏠 İlan Ekle" # Otomatik Sekme Değiştir
            st.rerun()

elif aktif_sekme == "🏠 İlan Ekle":
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        # Varsayılan olarak şehrin merkezini al, haritaya tıklandıysa tıklanan yeri al
        l_n, o_n, a_n = aktif_merkez[0], aktif_merkez[1], ""
        if st.session_state.get("prev_click"):
            l_n, o_n = st.session_state.prev_click["lat"], st.session_state.prev_click["lng"]
            a_n = koordinati_adrese_cevir(l_n, o_n)
            st.success(f"📍 Haritadan Konum Seçildi: {a_n}")
            
        with st.form("add_f"):
            ti, pr = st.text_input("Başlık (*Zorunlu*)"), st.number_input("Kira (TL) (*Zorunlu*)", min_value=0, step=500)
            c1, c2 = st.columns(2)
            rm = c1.selectbox("Oda Sayısı", ["1+0", "1+1", "2+1", "3+1", "4+1 ve üzeri"])
            fr = c2.checkbox("Eşyalı")
            ad, co = st.text_area("Adres (*Zorunlu*)", value=a_n), st.text_area("Açıklama")
            fl = st.file_uploader("Fotoğraf", type=["jpg", "png"])
            if st.form_submit_button("İlanı Yayınla"):
                if not icerik_uygun_mu(ti) or not icerik_uygun_mu(co): st.error("Kurallara aykırı kelime!")
                elif not ti or not ad or pr <= 0: st.error("Zorunlu alanları doldurun.")
                else:
                    b64 = ""
                    if fl:
                        img = Image.open(fl).convert("RGB")
                        img.thumbnail((600, 600))
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        b64 = base64.b64encode(buf.getvalue()).decode()
                    h_id = str(int(datetime.now().timestamp()))
                    h_data = {"id": h_id, "title": ti, "price": pr, "rooms": rm, "furnished": fr, "address": ad, "comment": co, "lat": l_n, "lon": o_n, "image": b64, "owner": st.session_state.current_user}
                    db.collection('houses').document(h_id).set(h_data)
                    st.session_state.houses.append(h_data)
                    st.session_state.prev_click = None # Sıfırla
                    st.success("İlan kaydedildi!")
                    st.session_state.active_tab = "📋 Tüm İlanlar" # Başarılıysa listeye at
                    st.rerun()

elif aktif_sekme == "📋 Tüm İlanlar":
    if not st.session_state.logged_in: st.warning("Giriş yapın.")
    else:
        st.info(f"📍 Şu an sadece **{secilen_sehir}** çevresindeki ilanlar listeleniyor.")
        for h in f_houses:
            esya_durumu = "Eşyalı" if h.get("furnished", False) else "Boş"
            oda_durumu = h.get("rooms", "Belirtilmemiş")
            with st.expander(f"🏠 {h['title']} - {h['price']} TL | {oda_durumu} - {esya_durumu}"):
                col1, col2 = st.columns([1, 2])
                if h.get("image"): col1.image(f"data:image/jpeg;base64,{h['image']}")
                col2.write(f"**Adres:** {h['address']}\n\n**Açıklama:** {h['comment']}")
                
                f_l = st.session_state.users[st.session_state.current_user].get("favorites", [])
                b1, b2, b3 = st.columns([1,1,2])
                with b1:
                    if st.button("❤️ Çıkar" if h["id"] in f_l else "🤍 Favorile", key=f"f_{h['id']}"):
                        if h["id"] in f_l: f_l.remove(h["id"])
                        else: f_l.append(h["id"])
                        db.collection('users').document(st.session_state.current_user).update({"favorites": f_l})
                        st.rerun()
                with b2:
                    if st.session_state.user_role == "yonetici" or h["owner"] == st.session_state.current_user:
                        if st.button("🗑️ Sil", key=f"s_{h['id']}"):
                            db.collection('houses').document(h["id"]).delete()
                            st.session_state.houses = [x for x in st.session_state.houses if x["id"] != h["id"]]
                            st.rerun()
                if h["owner"] != st.session_state.current_user:
                    st.markdown("---")
                    m_i = st.text_input("Mesajınız", key=f"m_{h['id']}")
                    if st.button("Gönder", key=f"b_{h['id']}"):
                        if m_i and icerik_uygun_mu(m_i):
                            msg = {"house": h["title"], "from": st.session_state.current_user, "to": h["owner"], "text": m_i, "date": datetime.now().strftime("%d.%m %H:%M")}
                            db.collection('messages').add(msg)
                            st.session_state.messages.append(msg)
                            st.success("İletildi.")

elif aktif_sekme == "⭐ Favoriler":
    if st.session_state.logged_in:
        f_l = st.session_state.users[st.session_state.current_user].get("favorites", [])
        for h in [x for x in st.session_state.houses if x["id"] in f_l]: 
            st.write(f"⭐ **{h['title']}** - {h['price']} TL")

elif aktif_sekme == "📩 Mesajlar":
    if st.session_state.logged_in:
        my_m = [m for m in st.session_state.messages if m["from"] == st.session_state.current_user or m["to"] == st.session_state.current_user or st.session_state.user_role == "yonetici"]
        for m in my_m:
            with st.chat_message("user" if m["from"] == st.session_state.current_user else "assistant"):
                st.write(f"**{m['house']}** | {m['from']} ➔ {m['to']}\n{m['text']}")

elif aktif_sekme == "📊 Admin":
    if st.session_state.user_role == "yonetici":
        st.header("📊 Admin İstatistikleri")
        c1, c2, c3 = st.columns(3)
        c1.metric("Kullanıcı", len(st.session_state.users))
        c2.metric("İlan", len(st.session_state.houses))
        c3.metric("Mesaj", len(st.session_state.messages))
