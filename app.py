import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Memur Emlak & Tayin Haritası", layout="wide")

# --- 1. ZARARLI İÇERİK FİLTRESİ ---
# Buraya engellemek istediğiniz tüm kelimeleri küçük harfle ekleyebilirsiniz.
YASAKLI_KELIMELER = ["aptal", "salak", "parti", "siyaset", "ırk", "defol", "lan"]

def icerik_uygun_mu(metin):
    metin_kucuk = metin.lower()
    for kelime in YASAKLI_KELIMELER:
        if kelime in metin_kucuk:
            return False
    return True

# --- 2. VERİ VE KULLANICI ALTYAPISI ---
# Kurumlar
institutions = [
    {"name": "Valilik", "lat": 38.6810, "lon": 39.2264},
    {"name": "Eğitim ve Araştırma Hastanesi", "lat": 38.6738, "lon": 39.1963},
    {"name": "Adliye", "lat": 38.6705, "lon": 39.2215}
]

# Hafızadaki Veriler
if 'houses' not in st.session_state:
    st.session_state.houses = []
    
# Örnek Kullanıcı Veritabanı
if 'users' not in st.session_state:
    st.session_state.users = {
        "admin": {"sifre": "admin123", "rol": "yonetici", "ad": "Sistem Yöneticisi"},
        "kullanici1": {"sifre": "1234", "rol": "kullanici", "ad": "Standart Memur"}
    }

# Oturum Durumu
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_role = None

# Mesafe Fonksiyonu
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

# --- 3. GİRİŞ EKRANI (ÜYE OLMAYANLAR İÇİN) ---
if not st.session_state.logged_in:
    st.title("🔐 Memur Tayin & Emlak Uygulamasına Giriş")
    st.info("Haritayı ve ilanları görebilmek için giriş yapmalısınız.")
    
    col_login, col_empty = st.columns([1, 2])
    with col_login:
        with st.form("login_form"):
            username = st.text_input("Kullanıcı Adı")
            password = st.text_input("Şifre", type="password")
            submit_login = st.form_submit_button("Giriş Yap")
            
            if submit_login:
                if username in st.session_state.users and st.session_state.users[username]["sifre"] == password:
                    st.session_state.logged_in = True
                    st.session_state.current_user = username
                    st.session_state.user_role = st.session_state.users[username]["rol"]
                    st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")
                    
    st.markdown("*(Test için Yönetici: `admin` Şifre: `admin123` | Kullanıcı: `kullanici1` Şifre: `1234`)*")

# --- 4. ANA UYGULAMA (GİRİŞ YAPANLAR İÇİN) ---
else:
    # Yan Menü (Sidebar)
    with st.sidebar:
        st.write(f"👤 **Hoş geldin, {st.session_state.users[st.session_state.current_user]['ad']}**")
        st.write(f"🛡️ **Yetki:** {st.session_state.user_role.upper()}")
        st.markdown("---")
        
        # Sadece Kendi İlanlarını Görme (Kullanıcı için)
        my_houses = [h for h in st.session_state.houses if h["owner"] == st.session_state.current_user]
        st.write(f"Sisteme eklediğiniz ilan sayısı: **{len(my_houses)}**")
        
        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.user_role = None
            st.rerun()

    st.title("🗺️ Memur Tayin & Emlak Uygulaması")
    
    # Sayfa Düzeni
    tab1, tab2, tab3 = st.tabs(["📍 Harita ve İlanlar", "🏠 Yeni İlan Ekle", "⚙️ Yönetim Paneli"])
    
    # --- SEKME 1: HARİTA ---
    with tab1:
        m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google Hybrid')

        for inst in institutions:
            folium.Marker(
                [inst["lat"], inst["lon"]],
                popup=f"<b>🏢 {inst['name']}</b>",
                tooltip=inst["name"],
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

        for house in st.session_state.houses:
            distances_html = "<ul>"
            for inst in institutions:
                dist = calculate_distance(house["lat"], house["lon"], inst["lat"], inst["lon"])
                distances_html += f"<li>{inst['name']}: {dist} km</li>"
            distances_html += "</ul>"

            image_html = ""
            if house.get('image_b64'):
                image_html = f'<img src="data:image/jpeg;base64,{house.get("image_b64")}" style="width:100%; border-radius:8px; margin-bottom:10px;">'

            popup_content = f"""
            <div style="width:220px">
                {image_html}
                <h4>{house['title']}</h4>
                <p style="color:green; font-size:16px;"><b>Kira:</b> {house['price']} TL</p>
                <p><b>Açıklama:</b> {house['comment']}</p>
                <p><small><b>Ekleyen:</b> {st.session_state.users[house['owner']]['ad']}</small></p>
                <b>Kurumlara Uzaklık:</b>
                {distances_html}
            </div>
            """
            
            folium.Marker(
                [house["lat"], house["lon"]],
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=house["title"],
                icon=folium.Icon(color="green", icon="home")
            ).add_to(m)

        map_data = st_folium(m, width="100%", height=500)

    # --- SEKME 2: İLAN EKLEME ---
    with tab2:
        st.markdown("### Yeni İlan Ekle")
        st.info("Haritadan tıkladığınız noktanın koordinatları otomatik olarak alınacaktır.")
        
        clicked_lat = 38.6748
        clicked_lon = 39.2225
        if map_data and map_data.get("last_clicked"):
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lon = map_data["last_clicked"]["lng"]

        with st.form("add_house_form"):
            title = st.text_input("İlan Başlığı (Örn: Hastaneye yakın 3+1)")
            price = st.number_input("Kira Ücreti (TL)", min_value=0, step=500)
            lat = st.number_input("Enlem", value=clicked_lat, format="%.6f")
            lon = st.number_input("Boylam", value=clicked_lon, format="%.6f")
            comment = st.text_area("Ev hakkında yorumlar (Küfür ve siyasi içerik yasaktır)")
            uploaded_file = st.file_uploader("Ev Fotoğrafı Yükle", type=["png", "jpg", "jpeg"])
            
            submitted = st.form_submit_button("İlanı Yayına Al")
            
            if submitted:
                # İÇERİK KONTROLÜ
                if not icerik_uygun_mu(title) or not icerik_uygun_mu(comment):
                    st.error("Uyarı: İlan başlığı veya açıklamasında sistem kurallarına aykırı kelimeler tespit edildi. Lütfen metninizi düzenleyin.")
                elif title and price > 0:
                    image_b64 = ""
                    if uploaded_file is not None:
                        image_b64 = base64.b64encode(uploaded_file.read()).decode()

                    new_house = {
                        "id": len(st.session_state.houses) + 1,
                        "title": title,
                        "price": price,
                        "lat": lat,
                        "lon": lon,
                        "comment": comment,
                        "image_b64": image_b64,
                        "owner": st.session_state.current_user # Evi kimin eklediğini kaydediyoruz
                    }
                    st.session_state.houses.append(new_house)
                    st.success("Ev başarıyla eklendi!")
                    st.rerun()
                else:
                    st.error("Lütfen geçerli bir başlık ve fiyat girin.")

    # --- SEKME 3: YÖNETİM VE DÜZENLEME PANELİ ---
    with tab3:
        st.markdown("### İlan Yönetimi")
        
        if len(st.session_state.houses) == 0:
            st.info("Sistemde henüz ilan bulunmuyor.")
        else:
            for idx, house in enumerate(st.session_state.houses):
                # Yönetici tüm ilanları görebilir ve silebilir. Kullanıcı sadece kendi ilanlarını yönetebilir.
                if st.session_state.user_role == "yonetici" or house["owner"] == st.session_state.current_user:
                    with st.expander(f"📌 {house['title']} - {house['price']} TL (Sahibi: {st.session_state.users[house['owner']]['ad']})"):
                        st.write(f"**Açıklama:** {house['comment']}")
                        
                        # Silme Butonu
                        if st.button(f"🗑️ Bu İlanı Sil", key=f"delete_{idx}"):
                            st.session_state.houses.pop(idx)
                            st.success("İlan silindi!")
                            st.rerun()
