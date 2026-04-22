import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import base64
from geopy.geocoders import Nominatim
from datetime import datetime

# --- 1. SAYFA VE GÖRÜNÜM AYARLARI ---
st.set_page_config(page_title="Memur Emlak & Tayin Portalı", layout="wide")

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
        geolocator = Nominatim(user_agent="memur_emlak_portal_v4")
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

# --- 4. VERİ TABANI BAŞLATMA ---
if 'houses' not in st.session_state: st.session_state.houses = []
if 'messages' not in st.session_state: st.session_state.messages = []
if 'users' not in st.session_state:
    st.session_state.users = {
        "misivi46": {"sifre": "Elvinmelek46**", "rol": "yonetici", "ad": "Sinan", "favorites": []}
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

# --- 5. YAN MENÜ (FİLTRELEME VE PROFİL) ---
with st.sidebar:
    st.title("👤 Üye Paneli")
    
    max_fiyat = 50000
    kurum_sec = "Farketmez"
    max_mesafe = 50.0

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
                        if "favorites" not in st.session_state.users[u]:
                            st.session_state.users[u]["favorites"] = []
                        st.rerun()
                    else: st.error("Hatalı bilgiler.")
        else:
            with st.form("s_form"):
                n_ad = st.text_input("Ad Soyad")
                n_u = st.text_input("Kullanıcı Adı")
                n_p = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt Ol"):
                    if n_ad and n_u and n_p:
                        st.session_state.users[n_u] = {"sifre": n_p, "rol": "kullanici", "ad": n_ad, "favorites": []}
                        st.success("Kayıt başarılı! Giriş yapabilirsiniz.")
    else:
        st.success(f"Merhaba, {st.session_state.users[st.session_state.current_user]['ad']}")
        
        with st.expander("🔍 Harita ve İlanları Filtrele", expanded=True):
            st.markdown("<small>Aşağıdaki ayarlar haritayı otomatik günceller.</small>", unsafe_allow_html=True)
            max_fiyat = st.slider("Maksimum Bütçe (TL)", 0, 50000, 50000, step=1000)
            kurum_sec = st.selectbox("Şu Kuruma Yakınlık:", ["Farketmez"] + [i["name"] for i in institutions])
            if kurum_sec != "Farketmez":
                max_mesafe = st.slider("Maksimum Mesafe (km)", 1.0, 30.0, 5.0, step=0.5)

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

# --- FİLTRELEME MANTIĞI ---
filtered_houses = []
for h in st.session_state.houses:
    if h["price"] <= max_fiyat:
        if kurum_sec == "Farketmez":
            filtered_houses.append(h)
        else:
            inst = next((i for i in institutions if i["name"] == kurum_sec), None)
            if inst:
                dist = calculate_distance(h["lat"], h["lon"], inst["lat"], inst["lon"])
                if dist <= max_mesafe:
                    filtered_houses.append(h)

# --- 6. ANA EKRAN ---
t1, t2, t3, t4, t5 = st.tabs(["📍 Harita", "🏠 İlan Ekle", "📋 İlanlar", "⭐ Favoriler", "📩 Mesajlar"])

# -- SEKME 1: HARİTA --
with t1:
    m = folium.Map(location=[38.6748, 39.2225], zoom_start=13, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    
    for inst in institutions:
        folium.Marker([inst["lat"], inst["lon"]], popup=inst["name"], icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
    
    if st.session_state.logged_in:
        for house in filtered_houses:
            dist_list = "<ul>"
            for inst in institutions:
                d = calculate_distance(house["lat"], house["lon"], inst["lat"], inst["lon"])
                dist_list += f"<li>{inst['name']}: {d} km</li>"
            dist_list += "</ul>"

            img_html = f'<img src="data:image/jpeg;base64,{house["image"]}" style="width:100%; border-radius:8px; margin-bottom:10px;">' if house.get("image") else ""

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
    else:
        st.info("👋 Haritada ilanları görmek için lütfen giriş yapın.")
        
    # ÇÖZÜMÜN UYGULANDIĞI YER: Sadece son tıklanan koordinatı çek, sayfa yenilenmesini (rerun) engelle
    map_res = st_folium(m, use_container_width=True, height=550, returned_objects=["last_clicked"])

# -- SEKME 2: İLAN EKLE --
with t2:
    if not st.session_state.logged_in: 
        st.warning("Lütfen ilan eklemek için önce giriş yapın.")
    else:
        lat_now, lon_now, addr_now = 38.6748, 39.2225, ""
        if map_res and map_res.get("last_clicked"):
            lat_now, lon_now = map_res["last_clicked"]["lat"], map_res["last_clicked"]["lng"]
            addr_now = koordinati_adrese_cevir(lat_now, lon_now)
            st.success(f"📍 Haritadan Konum Seçildi: {addr_now}")
            
        with st.form("h_form"):
            st.markdown("### Yeni İlan Detayları")
            h_t = st.text_input("İlan Başlığı (*Zorunlu*)")
            h_p = st.number_input("Aylık Kira (TL) (*Zorunlu*)", min_value=0, step=500)
            h_a = st.text_area("Açık Adres (*Zorunlu*)", value=addr_now)
            h_c = st.text_area("Açıklama")
            h_f = st.file_uploader("Fotoğraf (İsteğe Bağlı)", type=["jpg", "png", "jpeg"])
            
            submitted = st.form_submit_button("İlanı Yayınla")
            
            if submitted:
                if not icerik_uygun_mu(h_t) or not icerik_uygun_mu(h_c):
                    st.error("❌ Hata: İlan başlığı veya açıklamasında kurallara aykırı kelimeler tespit edildi.")
                elif not h_t or not h_a or h_p <= 0:
                    st.error("❌ Lütfen Başlık, Açık Adres ve 0'dan büyük bir Kira Bedeli girdiğinizden emin olun.")
                else:
                    b64 = base64.b64encode(h_f.read()).decode() if h_f is not None else ""
                    yeni_id = max([h["id"] for h in st.session_state.houses]) + 1 if st.session_state.houses else 1
                    
                    st.session_state.houses.append({
                        "id": yeni_id, 
                        "title": h_t, 
                        "price": h_p,
                        "address": h_a, 
                        "comment": h_c, 
                        "lat": lat_now, 
                        "lon": lon_now,
                        "image": b64, 
                        "owner": st.session_state.current_user
                    })
                    st.success("✅ İlanınız başarıyla eklendi! Haritadan veya İlanlar sekmesinden görebilirsiniz.")
                    st.rerun()

# -- SEKME 3: İLANLAR --
with t3:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        st.markdown(f"**Toplam Gösterilen İlan:** {len(filtered_houses)} *(Sol menüdeki filtrelere göredir)*")
        for house in filtered_houses:
            with st.expander(f"🏠 {house['title']} - {house['price']} TL"):
                c1, c2 = st.columns([1, 2])
                if house["image"]: c1.image(f"data:image/jpeg;base64,{house['image']}")
                c2.write(f"**Adres:** {house['address']}")
                c2.write(f"**Açıklama:** {house['comment']}")
                
                fav_list = st.session_state.users[st.session_state.current_user].get("favorites", [])
                is_fav = house["id"] in fav_list
                
                b1, b2, b3 = st.columns([1,1,2])
                with b1:
                    if st.button("❤️ Favoriden Çıkar" if is_fav else "🤍 Favoriye Ekle", key=f"fav_{house['id']}"):
                        if is_fav: fav_list.remove(house["id"])
                        else: fav_list.append(house["id"])
                        st.session_state.users[st.session_state.current_user]["favorites"] = fav_list
                        st.rerun()

                with b2:
                    if st.session_state.user_role == "yonetici" or house["owner"] == st.session_state.current_user:
                        if st.button("🗑️ İlanı Sil", key=f"del_{house['id']}"):
                            st.session_state.houses = [h for h in st.session_state.houses if h["id"] != house["id"]]
                            st.rerun()
                
                if house["owner"] != st.session_state.current_user:
                    st.markdown("---")
                    m_txt = st.text_input("İlan sahibine mesaj yazın", key=f"ti_{house['id']}")
                    if st.button("Mesaj Gönder", key=f"tb_{house['id']}"):
                        if m_txt and icerik_uygun_mu(m_txt):
                            st.session_state.messages.append({
                                "house": house["title"], "from": st.session_state.current_user,
                                "to": house["owner"], "text": m_txt, "date": datetime.now().strftime("%d.%m %H:%M")
                            })
                            st.success("Mesaj iletildi.")

# -- SEKME 4: FAVORİLER --
with t4:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        st.subheader("⭐ Kaydettiğiniz İlanlar")
        fav_list = st.session_state.users[st.session_state.current_user].get("favorites", [])
        fav_houses = [h for h in st.session_state.houses if h["id"] in fav_list]
        
        if not fav_houses:
            st.info("Henüz favorilerinize eklediğiniz bir ilan bulunmuyor.")
        else:
            for house in fav_houses:
                with st.container():
                    st.markdown(f"#### {house['title']} - {house['price']} TL")
                    st.write(f"📍 {house['address']}")
                    if st.button("💔 Favorilerden Kaldır", key=f"rem_fav_{house['id']}"):
                        fav_list.remove(house["id"])
                        st.session_state.users[st.session_state.current_user]["favorites"] = fav_list
                        st.rerun()
                    st.markdown("---")

# -- SEKME 5: MESAJLAR --
with t5:
    if not st.session_state.logged_in: st.warning("Giriş yapınız.")
    else:
        my_m = [m for m in st.session_state.messages if m["from"] == st.session_state.current_user or m["to"] == st.session_state.current_user or st.session_state.user_role == "yonetici"]
        if not my_m: st.info("Henüz mesajınız bulunmuyor.")
        for m in my_m:
            with st.chat_message("user" if m["from"] == st.session_state.current_user else "assistant"):
                st.write(f"**İlan:** {m['house']} | **Gönderen:** {st.session_state.users[m['from']]['ad']} ➔ **Alıcı:** {st.session_state.users[m['to']]['ad']}")
                st.write(m["text"])
                st.caption(m["date"])
