import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from datetime import datetime

# --- 1. SAYFA VE GÖRÜNÜM AYARLARI ---
st.set_page_config(page_title="Memur Emlak & Tayin Haritası", layout="wide")

# Haritanın çerçevenin dışına taşmasını engelleyen CSS
st.markdown("""
    <style>
        iframe {
            max-width: 100% !important;
            overflow: hidden !important;
            border-radius: 10px;
        }
        .main {
            background-color: #f5f7f9;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. ZARARLI İÇERİK FİLTRESİ ---
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "ırk", "defol", "lan"]

def icerik_uygun_mu(metin):
    metin_kucuk = metin.lower()
    for kelime in YASAKLI_KELIMELER:
        if kelime in metin_kucuk:
            return False
    return True

# --- 3. ADRES VE MESAFE FONKSİYONLARI ---
def koordinati_adrese_cevir(lat, lon):
    try:
        geolocator = Nominatim(user_agent="memur_emlak_portal")
        location = geolocator.reverse(f"{lat}, {lon}", timeout=3)
        return location.address if location else "Adres tespit edilemedi."
    except:
        return "Adres servisi şu an meşgul, lütfen manuel giriniz."

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 2)

# --- 4. VERİ TABANI SİMÜLASYONU ---
if 'houses' not in st.session_state: st.session_state.houses = []
if 'messages' not in st.session_state: st.session_state.messages = []
if 'users' not in st.session_state:
    st.session_state.users = {
        "misivi46": {"sifre": "Elvinmelek46**", "rol": "yonetici", "ad": "Sinan"}
    }

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_role = None

# Örnek Kurumlar (Elazığ)
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Fethi Sekin Şehir Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# --- 5. YAN MENÜ (AUTH & PROFİL) ---
with st.sidebar:
    st.title("👤 Üye Paneli")
    
    if not st.session_state.logged_in:
        if st.button("🌐 Google ile Giriş Yap", use_container_width=True):
            st.info("OAuth yapılandırması bekleniyor.")
            
        auth_mode = st.radio("İşlem:", ["Giriş Yap", "Üye Ol"])
        
        if auth_mode == "Giriş Yap":
            with st.form("l_form"):
                u = st.text_input("Kullanıcı Adı")
                p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş", use_container_width=True):
                    if u in st.session_state.users and st.session_state.users[u]["sifre"] == p:
                        st.session_state.logged_in, st.session_state.current_user = True, u
                        st.session_state.user_role = st.session_state.users[u]["rol"]
                        st.rerun()
                    else: st.error("Hatalı giriş.")
        else:
            with st.form("s_form"):
                n_ad = st.text_input("Ad Soyad")
                n_u = st.text_input("Kullanıcı Adı")
                n_p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt Ol"):
                    if n_ad and n_u and n_p:
                        st.session_state.users[n_u] = {"sifre": n_p, "rol": "kullanici", "ad": n_ad}
                        st.success("Kayıt tamam!")
    else:
        st.success(f"Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}")
        
        with st.expander("⚙️ Şifre Değiştir"):
            if st.session_state.user_role == "yonetici":
                target = st.selectbox("Üye Seç:", list(st.session_state.users.keys()))
                new_p = st.text_input("Yeni Şifre", type="password")
                if st.button("Şifreyi Güncelle"):
                    st.session_state.users[target]["sifre"] = new_p
                    st.success("İşlem başarılı.")
            else:
                old = st.text_input("Mevcut Şifre", type="password")
                new = st.text_input("Yeni Şifre", type="password")
                if st.button("Güncelle"):
                    if old == st.session_state.users[st.session_state.current_user]["sifre"]:
                        st.session_state.users[st.session_state.current_user]["sifre"] = new
                        st.success("Güncellendi.")

        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

# --- 6. ANA ARAYÜZ (TABS) ---
st.title("🗺️ Memur Emlak & Tayin Portalı")
t1, t2, t3, t4 = st.tabs(["📍 İlan Haritası", "🏠 İlan Ekle", "📋 İlan Yönetimi", "📩 Mesajlarım"])

# HARİTA SEKİMESİ
with t1:
    if not st.session_state.logged_in:
        st.info("İlanları görmek için lütfen giriş yapın. Kurum yerleri herkese açıktır.")
    
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    
    for inst in institutions:
        folium.Marker([inst["lat"], inst["lon"]], popup=inst["name"], icon=folium.Icon(color="blue", icon="briefcase", prefix='fa')).add_to(m)
    
    if st.session_state.logged_in:
        for house in st.session_state.houses:
            folium.Marker([house["lat"], house["lon"]], popup=f"<b>{house['title']}</b>", icon=folium.Icon(color="green", icon="home")).add_to(m)
    
    # Taşma sorunu çözülmüş harita bileşeni
    map_res = st_folium(m, use_container_width=True, height=550)

# İLAN EKLEME SEKİMESİ
with t2:
    if not st.session_state.logged_in: st.warning("Giriş yapmanız gerekmektedir.")
    else:
        st.subheader("Yeni İlan Oluştur")
        lat_now, lon_now, addr_now = 38.6748, 39.2225, ""
        if map_res and map_res.get("last_clicked"):
            lat_now = map_res["last_clicked"]["lat"]
            lon_now = map_res["last_clicked"]["lng"]
            addr_now = koordinati_adrese_cevir(lat_now, lon_now)
            st.success(f"Seçilen Adres: {addr_now}")
            
        with st.form("h_form"):
            h_t = st.text_input("İlan Başlığı")
            h_p = st.number_input("Aylık Kira (TL)", min_value=0)
            h_a = st.text_area("Açık Adres", value=addr_now)
            h_c = st.text_area("Detaylı Açıklama")
            h_f = st.file_uploader("Ev Fotoğrafı", type=["jpg", "png", "jpeg"])
            if st.form_submit_button("İlanı Yayınla"):
                if icerik_uygun_mu(h_t) and icerik_uygun_mu(h_c) and h_t and h_p > 0:
                    b64 = base64.b64encode(h_f.read()).decode() if h_f else ""
                    st.session_state.houses.append({
                        "id": len(st.session_state.houses)+1, "title": h_t, "price": h_p,
                        "address": h_a, "comment": h_c, "lat": lat_now, "lon": lon_now,
                        "image": b64, "owner": st.session_state.current_user
                    })
                    st.success("İlan eklendi!")
                    st.rerun()

# İLAN YÖNETİMİ VE İLETİŞİM
with t3:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        for i, house in enumerate(st.session_state.houses):
            with st.expander(f"🏠 {house['title']} - {house['price']} TL"):
                c1, c2 = st.columns([1, 2])
                if house["image"]: c1.image(f"data:image/jpeg;base64,{house['image']}")
                c2.write(f"**Adres:** {house['address']}")
                c2.write(f"**Açıklama:** {house['comment']}")
                
                # Mesaj Gönderme Bölümü
                if house["owner"] != st.session_state.current_user:
                    m_txt = st.text_input("İlan sahibine mesaj yazın", key=f"ti_{i}")
                    if st.button("Mesaj Gönder", key=f"tb_{i}"):
                        if m_txt and icerik_uygun_mu(m_txt):
                            st.session_state.messages.append({
                                "house": house["title"], "from": st.session_state.current_user,
                                "to": house["owner"], "text": m_txt, "date": datetime.now().strftime("%d.%m %H:%M")
                            })
                            st.success("Mesaj iletildi.")
                
                if st.session_state.user_role == "yonetici" or house["owner"] == st.session_state.current_user:
                    if st.button("🗑️ İlanı Kaldır", key=f"del_{i}"):
                        st.session_state.houses.pop(i)
                        st.rerun()

# MESAJLAR SEKİMESİ
with t4:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        my_m = [m for m in st.session_state.messages if m["from"] == st.session_state.current_user or m["to"] == st.session_state.current_user or st.session_state.user_role == "yonetici"]
        if not my_m: st.info("Mesaj trafiği yok.")
        for m in my_m:
            with st.chat_message("user" if m["from"] == st.session_state.current_user else "assistant"):
                st.write(f"**{m['house']}** hakkında")
                st.write(f"**{st.session_state.users[m['from']]['ad']}** ➔ **{st.session_state.users[m['to']]['ad']}**")
                st.write(m["text"])
                st.caption(m["date"])
