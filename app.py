import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Memur Emlak & Tayin Haritası", layout="wide")

# HARİTA TAŞMASINI ENGELLEYEN CSS KODU (Bunu ekle)
st.markdown("""
    <style>
        iframe {
            max-width: 100% !important;
            overflow: hidden !important;
        }
    </style>
""", unsafe_allow_html=True)
# --- 1. ZARARLI İÇERİK FİLTRESİ ---
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "irk", "defol", "lan"]

def icerik_uygun_mu(metin):
    metin_kucuk = metin.lower()
    for kelime in YASAKLI_KELIMELER:
        if kelime in metin_kucuk:
            return False
    return True

# --- KOORDİNATI ADRESE ÇEVİRME ---
def koordinati_adrese_cevir(lat, lon):
    try:
        geolocator = Nominatim(user_agent="memur_emlak_app_v2")
        location = geolocator.reverse(f"{lat}, {lon}", timeout=3)
        if location:
            return location.address
        return "Adres bulunamadı."
    except:
        return "Adres alınamadı."

# --- 2. VERİ ALTYAPISI ---
# Kurumlar
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Eğitim ve Araştırma Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# Hafızadaki Veriler
if 'houses' not in st.session_state:
    st.session_state.houses = []
    
if 'users' not in st.session_state:
    st.session_state.users = {
        "misivi46": {"sifre": "Elvinmelek46**", "rol": "yonetici", "ad": "Sinan"}
    }

# YENİ: Mesajlar Veritabanı
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Oturum Durumu
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_role = None

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

# --- 3. YAN MENÜ ---
with st.sidebar:
    st.title("🔑 Kullanıcı İşlemleri")
    
    if not st.session_state.logged_in:
        if st.button("🌐 Google Hesabı ile Devam Et", use_container_width=True):
            st.info("API bağlantısı kurulum aşamasındadır.")
            
        st.markdown("<div style='text-align: center; color: gray; margin: 10px 0;'>— Veya —</div>", unsafe_allow_html=True)
        secim = st.radio("İşlem Seçin:", ["Giriş Yap", "Üye Ol"], label_visibility="collapsed")
        
        if secim == "Giriş Yap":
            with st.form("login_form"):
                u_name = st.text_input("Kullanıcı Adı")
                u_pass = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap"):
                    if u_name in st.session_state.users and st.session_state.users[u_name]["sifre"] == u_pass:
                        st.session_state.logged_in = True
                        st.session_state.current_user = u_name
                        st.session_state.user_role = st.session_state.users[u_name]["rol"]
                        st.rerun()
                    else:
                        st.error("Hatalı bilgiler!")
                        
        elif secim == "Üye Ol":
            with st.form("signup_form"):
                y_ad = st.text_input("Ad Soyad*")
                y_kullanici = st.text_input("Kullanıcı Adı*")
                y_sifre = st.text_input("Şifre*", type="password")
                if st.form_submit_button("Kayıt Ol"):
                    if y_ad and y_kullanici and y_sifre:
                        st.session_state.users[y_kullanici] = {"sifre": y_sifre, "rol": "kullanici", "ad": y_ad}
                        st.success("Kaydolundu! Giriş yapabilirsiniz.")

    else:
        st.success(f"Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}")
        
        # Profil Ayarları
        with st.expander("⚙️ Profil Ayarları"):
            if st.session_state.user_role == "yonetici":
                target = st.selectbox("Kullanıcı Seç:", list(st.session_state.users.keys()))
                new_pw = st.text_input("Yeni Şifre", type="password")
                if st.button("Şifreyi Sıfırla"):
                    st.session_state.users[target]["sifre"] = new_pw
                    st.success("Güncellendi.")
            else:
                old_p = st.text_input("Eski Şifre", type="password")
                new_p = st.text_input("Yeni Şifre", type="password")
                if st.button("Şifremi Değiştir"):
                    if old_p == st.session_state.users[st.session_state.current_user]["sifre"]:
                        st.session_state.users[st.session_state.current_user]["sifre"] = new_p
                        st.success("Değiştirildi.")

        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()

# --- 4. ANA EKRAN ---
st.title("🗺️ Memur Tayin & Emlak Uygulaması")

tab_h, tab_e, tab_y, tab_m = st.tabs(["📍 Harita", "🏠 İlan Ekle", "⚙️ Yönetim", "💬 Mesajlarım"])

# -- TAB 1: HARİTA --
with tab_h:
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google Hybrid')

    for inst in institutions:
        folium.Marker([inst["lat"], inst["lon"]], popup=inst["name"], icon=folium.Icon(color="blue")).add_to(m)

    if st.session_state.logged_in:
        for house in st.session_state.houses:
            popup_text = f"<b>{house['title']}</b><br>Kira: {house['price']} TL"
            folium.Marker([house["lat"], house["lon"]], popup=popup_text, icon=folium.Icon(color="green", icon="home")).add_to(m)

    map_data = st_folium(m, width="100%", height=500)

# -- TAB 2: İLAN EKLE --
with tab_e:
    if not st.session_state.logged_in:
        st.warning("Giriş yapmalısınız.")
    else:
        # Adres çekme işlemi
        lat_c, lon_c = 38.6748, 39.2225
        auto_addr = ""
        if map_data and map_data.get("last_clicked"):
            lat_c = map_data["last_clicked"]["lat"]
            lon_c = map_data["last_clicked"]["lng"]
            auto_addr = koordinati_adrese_cevir(lat_c, lon_c)

        with st.form("add_form"):
            t = st.text_input("Başlık")
            p = st.number_input("Kira", min_value=0)
            a = st.text_area("Açık Adres", value=auto_addr)
            c = st.text_area("Açıklama")
            img = st.file_uploader("Fotoğraf", type=["jpg", "png"])
            if st.form_submit_button("Ekle"):
                if icerik_uygun_mu(t) and icerik_uygun_mu(c) and t and p > 0:
                    img_b64 = base64.b64encode(img.read()).decode() if img else ""
                    st.session_state.houses.append({
                        "id": len(st.session_state.houses) + 1, "title": t, "price": p,
                        "lat": lat_c, "lon": lon_c, "address": a, "comment": c,
                        "image_b64": img_b64, "owner": st.session_state.current_user
                    })
                    st.success("Eklendi.")
                    st.rerun()

# -- TAB 3: YÖNETİM VE İLAN DETAY (MESAJLAŞMA BURADA) --
with tab_y:
    if not st.session_state.logged_in:
        st.warning("Giriş yapmalısınız.")
    else:
        st.subheader("İlan Detayları ve İletişim")
        for idx, house in enumerate(st.session_state.houses):
            with st.expander(f"📌 {house['title']} - {house['price']} TL"):
                col_i, col_d = st.columns([1, 2])
                with col_i:
                    if house.get('image_b64'):
                        st.image(f"data:image/jpeg;base64,{house['image_b64']}")
                with col_d:
                    st.write(f"**Adres:** {house['address']}")
                    st.write(f"**Açıklama:** {house['comment']}")
                    st.write(f"**Sahibi:** {st.session_state.users[house['owner']]['ad']}")
                
                st.markdown("---")
                # MESAJ GÖNDERME BÖLÜMÜ
                if house["owner"] != st.session_state.current_user:
                    st.write("📩 **İlan Sahibiyle İletişime Geç**")
                    msg_text = st.text_input("Mesajınız", key=f"msg_input_{idx}")
                    if st.button("Gönder", key=f"send_btn_{idx}"):
                        if msg_text and icerik_uygun_mu(msg_text):
                            st.session_state.messages.append({
                                "house_id": house["id"],
                                "sender": st.session_state.current_user,
                                "receiver": house["owner"],
                                "text": msg_text,
                                "time": datetime.now().strftime("%H:%M")
                            })
                            st.success("Mesaj gönderildi!")
                        else:
                            st.error("Geçersiz içerik.")
                
                if st.session_state.user_role == "yonetici" or house["owner"] == st.session_state.current_user:
                    if st.button(f"🗑️ İlanı Sil", key=f"del_{idx}"):
                        st.session_state.houses.pop(idx)
                        st.rerun()

# -- TAB 4: MESAJLARIM (ÖZEL İLETİŞİM) --
with tab_m:
    if not st.session_state.logged_in:
        st.warning("Mesajlarınızı görmek için giriş yapın.")
    else:
        st.subheader("Gelen ve Giden Mesajlar")
        # Gizlilik Filtresi: Sadece gönderen, alan veya admin görebilir
        relevant_msgs = [m for m in st.session_state.messages if 
                         m["sender"] == st.session_state.current_user or 
                         m["receiver"] == st.session_state.current_user or 
                         st.session_state.user_role == "yonetici"]
        
        if not relevant_msgs:
            st.info("Henüz mesajınız bulunmuyor.")
        else:
            for m in relevant_msgs:
                sender_name = st.session_state.users[m['sender']]['ad']
                receiver_name = st.session_state.users[m['receiver']]['ad']
                
                # Mesajın hangi ilanla ilgili olduğunu bulalım
                h_title = next((h["title"] for h in st.session_state.houses if h["id"] == m["house_id"]), "Silinmiş İlan")
                
                with st.chat_message("user" if m["sender"] == st.session_state.current_user else "assistant"):
                    st.write(f"**İlan:** {h_title}")
                    st.write(f"**Kimden:** {sender_name} ➔ **Kime:** {receiver_name}")
                    st.write(m["text"])
                    st.caption(f"Saat: {m['time']}")
