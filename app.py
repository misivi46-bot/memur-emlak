import streamlit as st
import folium
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

# --- 1. SAYFA AYARLARI VE TAŞMA ENGELLEYİCİ ---
st.set_page_config(page_title="Memur Emlak & Tayin Portalı", layout="wide")

st.markdown("""
    <style>
        iframe { max-width: 100% !important; overflow: hidden !important; border-radius: 12px; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .main { background-color: #f8f9fa; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FIREBASE BAĞLANTISI (SECRETS ÜZERİNDEN) ---
@st.cache_resource
def get_db():
    try:
        # Streamlit Secrets'a eklediğin anahtarı çekiyoruz
        key_dict = json.loads(st.secrets["firebase_key"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds)
    except Exception as e:
        st.error(f"Veritabanına bağlanılamadı. Lütfen Secrets kısmını kontrol edin. Hata: {e}")
        return None

db = get_db()

# --- 3. VERİ YÜKLEME FONKSİYONLARI ---
def load_data():
    if db is None: return
    # Kullanıcıları çek
    users = db.collection('users').stream()
    st.session_state.users = {doc.id: doc.to_dict() for doc in users}
    
    # Yönetici hesabını (misivi46) DB'de yoksa oluştur
    if "misivi46" not in st.session_state.users:
        admin_data = {"sifre": "Elvinmelek46**", "rol": "yonetici", "ad": "Sinan", "favorites": []}
        db.collection('users').document("misivi46").set(admin_data)
        st.session_state.users["misivi46"] = admin_data

    # İlanları çek
    houses = db.collection('houses').stream()
    st.session_state.houses = [doc.to_dict() for doc in houses]
    
    # Mesajları çek
    msgs = db.collection('messages').stream()
    st.session_state.messages = [doc.to_dict() for doc in msgs]

if 'data_loaded' not in st.session_state:
    st.session_state.users = {}
    st.session_state.houses = []
    st.session_state.messages = []
    load_data()
    st.session_state.data_loaded = True

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None

# --- 4. YARDIMCI ARAÇLAR ---
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "ırk", "defol", "lan"]

def icerik_uygun_mu(metin):
    metin_k = metin.lower()
    return not any(kelime in metin_k for kelime in YASAKLI_KELIMELER)

def koordinati_adrese_cevir(lat, lon):
    try:
        geolocator = Nominatim(user_agent="memur_emlak_final")
        loc = geolocator.reverse(f"{lat}, {lon}", timeout=3)
        return loc.address if loc else "Adres bulunamadı."
    except: return "Adres servisi meşgul."

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 2)

institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Fethi Sekin Şehir Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# --- 5. SIDEBAR (AUTH & FİLTRELER) ---
with st.sidebar:
    st.title("🏡 İşlemler")
    max_fiyat, kurum_sec, max_mesafe = 50000, "Farketmez", 50.0

    if not st.session_state.logged_in:
        auth = st.radio("Seçim:", ["Giriş Yap", "Üye Ol"])
        if auth == "Giriş Yap":
            with st.form("l_f"):
                u, p = st.text_input("Kullanıcı Adı"), st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş"):
                    load_data() # Güncel veriyi çek
                    if u in st.session_state.users and st.session_state.users[u]["sifre"] == p:
                        st.session_state.logged_in, st.session_state.current_user = True, u
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
        with st.expander("🔍 İlanları Filtrele", expanded=True):
            max_fiyat = st.slider("Maks. Bütçe", 0, 50000, 50000, step=500)
            kurum_sec = st.selectbox("Kuruma Yakınlık:", ["Farketmez"] + [i["name"] for i in institutions])
            if kurum_sec != "Farketmez": max_mesafe = st.slider("Mesafe (km)", 0.5, 20.0, 5.0)

        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()

# Filtreleme
f_houses = [h for h in st.session_state.houses if h["price"] <= max_fiyat]
if kurum_sec != "Farketmez":
    inst = next(i for i in institutions if i["name"] == kurum_sec)
    f_houses = [h for h in f_houses if calculate_distance(h["lat"], h["lon"], inst["lat"], inst["lon"]) <= max_mesafe]

# --- 6. ANA PANEL ---
t1, t2, t3, t4, t5 = st.tabs(["📍 Harita", "🏠 İlan Ekle", "📋 Tüm İlanlar", "⭐ Favoriler", "📩 Mesajlar"])

with t1:
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    for i in institutions: folium.Marker([i["lat"], i["lon"]], popup=i["name"], icon=folium.Icon(color="blue", icon="briefcase", prefix='fa')).add_to(m)
    
    if st.session_state.logged_in:
        for h in f_houses:
            # Hata engelleyici: house.get kullanarak güvenli veri çekme
            img_b64 = h.get("image", "")
            img_tag = f'<img src="data:image/jpeg;base64,{img_b64}" style="width:100%; border-radius:8px; margin-bottom:8px;">' if img_b64 else ""
            popup_html = f"<div style='width:220px;'>{img_tag}<b>{h['title']}</b><br><span style='color:green;'>{h['price']} TL</span><br><small>{h['address']}</small></div>"
            folium.Marker([h["lat"], h["lon"]], popup=folium.Popup(popup_html, max_width=250), icon=folium.Icon(color="green", icon="home")).add_to(m)
    else: st.info("İlanları görmek için giriş yapın.")
    # Zoom sorununu çözen parametreler
    m_res = st_folium(m, use_container_width=True, height=550, returned_objects=["last_clicked"])

with t2:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        st.subheader("Yeni İlan")
        l_n, o_n, a_n = 38.6748, 39.2225, ""
        if m_res and m_res.get("last_clicked"):
            l_n, o_n = m_res["last_clicked"]["lat"], m_res["last_clicked"]["lng"]
            a_n = koordinati_adrese_cevir(l_n, o_n)
            st.success(f"Seçilen Konum: {a_n}")
            
        with st.form("add_f"):
            ti, pr = st.text_input("Başlık"), st.number_input("Kira (TL)", min_value=0)
            ad, co = st.text_area("Adres", value=a_n), st.text_area("Açıklama")
            fl = st.file_uploader("Fotoğraf", type=["jpg", "png"])
            if st.form_submit_button("İlanı Yayınla"):
                if icerik_uygun_mu(ti) and icerik_uygun_mu(co) and ti and pr > 0:
                    b64 = ""
                    if fl:
                        img = Image.open(fl).convert("RGB")
                        img.thumbnail((600, 600)) # Boyutu küçült (DB tasarrufu)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        b64 = base64.b64encode(buf.getvalue()).decode()
                    
                    h_id = str(int(datetime.now().timestamp())) # Benzersiz ID
                    h_data = {"id": h_id, "title": ti, "price": pr, "address": ad, "comment": co, "lat": l_n, "lon": o_n, "image": b64, "owner": st.session_state.current_user}
                    db.collection('houses').document(h_id).set(h_data)
                    st.success("İlan veritabanına kaydedildi!")
                    st.rerun()

with t3:
    if not st.session_state.logged_in: st.warning("Giriş yapın.")
    else:
        for h in f_houses:
            with st.expander(f"🏠 {h['title']} - {h['price']} TL"):
                col1, col2 = st.columns([1, 2])
                if h.get("image"): col1.image(f"data:image/jpeg;base64,{h['image']}")
                col2.write(f"**Adres:** {h['address']}\n\n**Açıklama:** {h['comment']}")
                
                # Favori & Silme & Mesaj
                f_l = st.session_state.users[st.session_state.current_user].get("favorites", [])
                if st.button("❤️" if h["id"] in f_l else "🤍", key=f"f_{h['id']}"):
                    if h["id"] in f_l: f_l.remove(h["id"])
                    else: f_l.append(h["id"])
                    db.collection('users').document(st.session_state.current_user).update({"favorites": f_l})
                    st.rerun()
                
                if st.session_state.user_role == "yonetici" or h["owner"] == st.session_state.current_user:
                    if st.button("🗑️ Sil", key=f"s_{h['id']}"):
                        db.collection('houses').document(h["id"]).delete()
                        st.rerun()
                
                if h["owner"] != st.session_state.current_user:
                    m_i = st.text_input("Mesajınız", key=f"m_{h['id']}")
                    if st.button("Gönder", key=f"b_{h['id']}"):
                        if m_i and icerik_uygun_mu(m_i):
                            db.collection('messages').add({"house": h["title"], "from": st.session_state.current_user, "to": h["owner"], "text": m_i, "date": datetime.now().strftime("%H:%M")})
                            st.success("Gönderildi.")

with t4:
    if st.session_state.logged_in:
        f_l = st.session_state.users[st.session_state.current_user].get("favorites", [])
        favs = [h for h in st.session_state.houses if h["id"] in f_l]
        if not favs: st.info("Favori ilan yok.")
        for h in favs: st.write(f"⭐ **{h['title']}** - {h['price']} TL (Adres: {h['address']})")

with t5:
    if st.session_state.logged_in:
        my_m = [m for m in st.session_state.messages if m["from"] == st.session_state.current_user or m["to"] == st.session_state.current_user or st.session_state.user_role == "yonetici"]
        for m in my_m:
            with st.chat_message("user" if m["from"] == st.session_state.current_user else "assistant"):
                st.write(f"**{m['house']}** | {m['from']} ➔ {m['to']}\n{m['text']}")
