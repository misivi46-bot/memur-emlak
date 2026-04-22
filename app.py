import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from datetime import datetime

# --- 1. SAYFA VE GÖRÜNÜM AYARLARI ---
st.set_page_config(page_title="Memur Emlak & Tayin Portalı", layout="wide")

# Haritanın dışa taşmasını engelleyen CSS
st.markdown("""
    <style>
        iframe {
            max-width: 100% !important;
            overflow: hidden !important;
            border-radius: 12px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. İÇERİK FİLTRESİ ---
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
        geolocator = Nominatim(user_agent="memur_emlak_portal_sinan")
        location = geolocator.reverse(f"{lat}, {lon}", timeout=3)
        return location.address if location else "Adres tespit edilemedi."
    except:
        return "Adres servisi şu an meşgul."

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a))), 2)

# --- 4. VERİ TABANI ---
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

institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Fethi Sekin Şehir Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# --- 5. YAN MENÜ ---
with st.sidebar:
    st.title("👤 Üye Paneli")
    
    if not st.session_state.logged_in:
        auth_mode = st.radio("İşlem Seçin:", ["Giriş Yap", "Üye Ol"])
        if auth_mode == "Giriş Yap":
            with st.form("l_form"):
                u = st.text_input("Kullanıcı Adı")
                p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap"):
                    if u in st.session_state.users and st.session_state.users[u]["sifre"] == p:
                        st.session_state.logged_in, st.session_state.current_user = True, u
                        st.session_state.user_role = st.session_state.users[u]["rol"]
                        st.rerun()
                    else: st.error("Hatalı bilgiler.")
        else:
            with st.form("s_form"):
                n_ad = st.text_input("Ad Soyad")
                n_u = st.text_input("Kullanıcı Adı")
                n_p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt Ol"):
                    if n_ad and n_u and n_p:
                        st.session_state.users[n_u] = {"sifre": n_p, "rol": "kullanici", "ad": n_ad}
                        st.success("Kayıt başarılı!")
    else:
        st.success(f"Merhaba, {st.session_state.users[st.session_state.current_user]['ad']}")
        with st.expander("⚙️ Şifre İşlemleri"):
            if st.session_state.user_role == "yonetici":
                target = st.selectbox("Üye:", list(st.session_state.users.keys()))
                new_p = st.text_input("Yeni Şifre", type="password")
                if st.button("Güncelle"):
                    st.session_state.users[target]["sifre"] = new_p
                    st.success("Şifre değiştirildi.")
            else:
                old = st.text_input("Eski Şifre", type="password")
                new = st.text_input("Yeni Şifre", type="password")
                if st.button("Şifremi Değiştir"):
                    if old == st.session_state.users[st.session_state.current_user]["sifre"]:
                        st.session_state.users[st.session_state.current_user]["sifre"] = new
                        st.success("Şifreniz güncellendi.")
        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()

# --- 6. ANA EKRAN ---
t1, t2, t3, t4 = st.tabs(["📍 Harita", "🏠 İlan Ekle", "📋 İlan Detayları", "📩 Mesajlarım"])

with t1:
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    
    for inst in institutions:
        folium.Marker([inst["lat"], inst["lon"]], popup=inst["name"], icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
    
    if st.session_state.logged_in:
        for house in st.session_state.houses:
            # Uzaklıkları hesapla
            dist_list = "<ul>"
            for inst in institutions:
                d = calculate_distance(house["lat"], house["lon"], inst["lat"], inst["lon"])
                dist_list += f"<li>{inst['name']}: {d} km</li>"
            dist_list += "</ul>"

            # Görseli hazırla
            img_html = ""
            if house.get("image"):
                img_html = f'<img src="data:image/jpeg;base64,{house["image"]}" style="width:100%; border-radius:8px; margin-bottom:10px;">'

            # Popup içeriğini oluştur
            popup_content = f"""
            <div style="width:230px; font-family: sans-serif;">
                {img_html}
                <h4 style="margin:0 0 5px 0;">{house['title']}</h4>
                <p style="color:#27ae60; font-size:16px; font-weight:bold; margin:0;">Kira: {house['price']} TL</p>
                <p style="font-size:12px; margin:5px 0;"><b>Adres:</b> {house['address']}</p>
                <p style="font-size:12px; color:#555;">{house['comment']}</p>
                <hr style="margin:10px 0;">
                <p style="font-size:11px;"><b>Kurumlara Uzaklık:</b></p>
                {dist_list}
            </div>
            """
            folium.Marker(
                [house["lat"], house["lon"]], 
                popup=folium.Popup(popup_content, max_width=300), 
                icon=folium.Icon(color="green", icon="home")
            ).add_to(m)
    
    map_res = st_folium(m, use_container_width=True, height=550)

with t2:
    if not st.session_state.logged_in: st.warning("Lütfen giriş yapın.")
    else:
        lat_now, lon_now, addr_now = 38.6748, 39.2225, ""
        if map_res and map_res.get("last_clicked"):
            lat_now, lon_now = map_res["last_clicked"]["lat"], map_res["last_clicked"]["lng"]
            addr_now = koordinati_adrese_cevir(lat_now, lon_now)
            st.success(f"📍 Konum Seçildi: {addr_now}")
            
        with st.form("h_form"):
            h_t = st.text_input("İlan Başlığı")
            h_p = st.number_input("Aylık Kira (TL)", min_value=0)
            h_a = st.text_area("Açık Adres", value=addr_now)
            h_c = st.text_area("Açıklama")
            h_f = st.file_uploader("Fotoğraf", type=["jpg", "png", "jpeg"])
            if st.form_submit_button("Yayınla"):
                if icerik_uygun_mu(h_t) and icerik_uygun_mu(h_c) and h_t and h_p > 0:
                    b64 = base64.b64encode(h_f.read()).decode() if h_f else ""
                    st.session_state.houses.append({
                        "id": len(st.session_state.houses)+1, "title": h_t, "price": h_p,
                        "address": h_a, "comment": h_c, "lat": lat_now, "lon": lon_now,
                        "image": b64, "owner": st.session_state.current_user
                    })
                    st.success("İlan eklendi!")
                    st.rerun()

with t3:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        for i, house in enumerate(st.session_state.houses):
            with st.expander(f"🏠 {house['title']} - {house['price']} TL"):
                c1, c2 = st.columns([1, 2])
                if house["image"]: c1.image(f"data:image/jpeg;base64,{house['image']}")
                c2.write(f"**Adres:** {house['address']}")
                c2.write(f"**Açıklama:** {house['comment']}")
                if house["owner"] != st.session_state.current_user:
                    m_txt = st.text_input("Mesajınız", key=f"ti_{i}")
                    if st.button("Gönder", key=f"tb_{i}"):
                        if m_txt and icerik_uygun_mu(m_txt):
                            st.session_state.messages.append({
                                "house": house["title"], "from": st.session_state.current_user,
                                "to": house["owner"], "text": m_txt, "date": datetime.now().strftime("%d.%m %H:%M")
                            })
                            st.success("Mesaj gönderildi.")
                if st.session_state.user_role == "yonetici" or house["owner"] == st.session_state.current_user:
                    if st.button("🗑️ Sil", key=f"del_{i}"):
                        st.session_state.houses.pop(i)
                        st.rerun()

with t4:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        my_m = [m for m in st.session_state.messages if m["from"] == st.session_state.current_user or m["to"] == st.session_state.current_user or st.session_state.user_role == "yonetici"]
        if not my_m: st.info("Mesaj yok.")
        for m in my_m:
            with st.chat_message("user" if m["from"] == st.session_state.current_user else "assistant"):
                st.write(f"**{m['house']}** | {st.session_state.users[m['from']]['ad']} ➔ {st.session_state.users[m['to']]['ad']}")
                st.write(m["text"])
                st.caption(m["date"])
