import os
import json
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'çok_gizli_bir_anahtar_değiştir_bunu'

# ---------- SMART CURSOR (SQLite/PostgreSQL uyumlu) ----------
class SmartCursor:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.is_sqlite = isinstance(conn, sqlite3.Connection)

    def execute(self, query, params=None):
        if self.is_sqlite and params is not None:
            query = query.replace('%s', '?')
        if params is not None:
            return self.cursor.execute(query, params)
        else:
            return self.cursor.execute(query)

    def executemany(self, query, params_list):
        if self.is_sqlite and params_list:
            query = query.replace('%s', '?')
        return self.cursor.executemany(query, params_list)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self.cursor, name)

# ---------- VERİTABANI BAĞLANTI ----------
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn
    else:
        return psycopg2.connect(DATABASE_URL)

# ---------- VERİTABANI KURULUMU ----------
def veritabani_kur():
    conn = get_db_connection()
    cursor = SmartCursor(conn)

    # Kullanıcı tablosu
    if isinstance(conn, sqlite3.Connection):
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    else:
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

    # Oyun kaydı
    cursor.execute('''CREATE TABLE IF NOT EXISTS oyun_kaydi (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        bakiye REAL DEFAULT 0,
        taraftar INTEGER DEFAULT 0,
        tiklamaGucu REAL DEFAULT 1,
        saniyeGeliri REAL DEFAULT 0,
        marketEsyalari TEXT,
        level INTEGER DEFAULT 1,
        xp REAL DEFAULT 0,
        mesajlar TEXT DEFAULT '[]',
        alinan_oduller TEXT DEFAULT '[]',
        prestij INTEGER DEFAULT 0,
        personeller TEXT,
        toplam_tiklama INTEGER DEFAULT 0,
        son_giris TIMESTAMP,
        gunluk_odul_alinmis BOOLEAN DEFAULT FALSE
    )''')

    # Yayın istatistikleri
    cursor.execute('''CREATE TABLE IF NOT EXISTS yayin_istatistikleri (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        toplam_yayin_suresi INTEGER DEFAULT 0,
        toplam_kazanilan_para REAL DEFAULT 0,
        toplam_kazanilan_taraftar INTEGER DEFAULT 0,
        toplam_tiklama INTEGER DEFAULT 0,
        en_yuksek_gelir REAL DEFAULT 0
    )''')

    # Liderlik
    cursor.execute('''CREATE TABLE IF NOT EXISTS liderlik (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        prestij INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        toplam_gelir REAL DEFAULT 0,
        toplam_taraftar INTEGER DEFAULT 0,
        son_guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Başarımlar
    cursor.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        icon TEXT,
        condition_type TEXT,
        condition_value INTEGER,
        reward_type TEXT,
        reward_amount INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_achievements (
        user_id INTEGER REFERENCES users(id),
        achievement_id INTEGER,
        unlocked_at TIMESTAMP,
        PRIMARY KEY (user_id, achievement_id)
    )''')

    # Günlük görevler
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_quests (
        id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        condition_type TEXT,
        condition_value INTEGER,
        reward_type TEXT,
        reward_amount INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_quest_progress (
        user_id INTEGER REFERENCES users(id),
        quest_id INTEGER,
        progress INTEGER DEFAULT 0,
        completed BOOLEAN DEFAULT FALSE,
        date DATE,
        PRIMARY KEY (user_id, quest_id, date)
    )''')

    # Stüdyo dekorasyonları
    cursor.execute('''CREATE TABLE IF NOT EXISTS studio_decorations (
        id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        icon TEXT,
        price INTEGER,
        bonus_type TEXT,
        bonus_value REAL,
        is_special BOOLEAN DEFAULT FALSE,
        required_prestige INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_decorations (
        user_id INTEGER REFERENCES users(id),
        decoration_id INTEGER,
        purchased_at TIMESTAMP,
        equipped BOOLEAN DEFAULT FALSE,
        PRIMARY KEY (user_id, decoration_id)
    )''')

    # Loot kutuları
    cursor.execute('''CREATE TABLE IF NOT EXISTS loot_boxes (
        id INTEGER PRIMARY KEY,
        name TEXT,
        reward_pool TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_loot_history (
        user_id INTEGER REFERENCES users(id),
        loot_id INTEGER,
        reward_type TEXT,
        reward_amount REAL,
        opened_at TIMESTAMP
    )''')

    # Prestij özel eşyaları
    cursor.execute('''CREATE TABLE IF NOT EXISTS prestige_special_items (
        id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        icon TEXT,
        required_prestige INTEGER,
        bonus_type TEXT,
        bonus_value REAL
    )''')

    # AI rakipleri
    cursor.execute('''CREATE TABLE IF NOT EXISTS ai_opponents (
        id INTEGER PRIMARY KEY,
        name TEXT,
        icon TEXT,
        income REAL,
        followers INTEGER,
        level INTEGER,
        growth_rate REAL,
        last_updated TIMESTAMP
    )''')

    # Etkinlikler
    cursor.execute('''CREATE TABLE IF NOT EXISTS etkinlikler (
        id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        baslangic TIMESTAMP,
        bitis TIMESTAMP,
        reward_type TEXT,
        reward_amount REAL,
        aktif BOOLEAN DEFAULT TRUE
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kullanici_etkinlik_progress (
        user_id INTEGER REFERENCES users(id),
        etkinlik_id INTEGER,
        progress INTEGER DEFAULT 0,
        tamamlandi BOOLEAN DEFAULT FALSE,
        PRIMARY KEY (user_id, etkinlik_id)
    )''')

    # Varsayılan veriler
    cursor.execute('SELECT COUNT(*) FROM achievements')
    if cursor.fetchone()[0] == 0:
        basarimlar = [
            (1, 'İlk Tıklama', 'İlk yayınını yap!', '👆', 'toplam_tiklama', 1, 'taraftar', 5),
            (2, '100 Tıklama', '100 kez yayın yap.', '🖱️', 'toplam_tiklama', 100, 'bakiye', 100),
            (3, '1000 Tıklama', '1000 kez yayın yap.', '🔥', 'toplam_tiklama', 1000, 'tiklamaGucu', 5),
            (4, '10000 Tıklama', '10000 kez yayın yap.', '💪', 'toplam_tiklama', 10000, 'bakiye', 5000),
            (5, '100 Taraftar', '100 taraftara ulaş.', '👥', 'taraftar_sayisi', 100, 'taraftar', 20),
            (6, '1000 Taraftar', '1000 taraftara ulaş.', '👨‍👩‍👧‍👦', 'taraftar_sayisi', 1000, 'bakiye', 1000),
            (7, '10000 Taraftar', '10000 taraftara ulaş.', '🌟', 'taraftar_sayisi', 10000, 'carpan', 0.1),
            (8, '100₺ Gelir', 'Saniyede 100₺ pasif gelir elde et.', '💰', 'saniye_geliri', 100, 'bakiye', 500),
            (9, '1000₺ Gelir', 'Saniyede 1000₺ pasif gelir elde et.', '💎', 'saniye_geliri', 1000, 'taraftar', 200),
            (10, 'Seviye 10', 'Seviye 10\'a ulaş.', '🎯', 'level', 10, 'tiklamaGucu', 10),
            (11, 'Seviye 25', 'Seviye 25\'e ulaş.', '🏅', 'level', 25, 'carpan', 0.2),
            (12, 'İlk Prestij', 'İlk prestijini yap.', '♻️', 'prestij_sayisi', 1, 'carpan', 0.5),
        ]
        cursor.executemany('INSERT INTO achievements (id, name, description, icon, condition_type, condition_value, reward_type, reward_amount) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', basarimlar)

    cursor.execute('SELECT COUNT(*) FROM daily_quests')
    if cursor.fetchone()[0] == 0:
        gorevler = [
            (1, 'Yayıncı Ruhu', '50 kez tıkla', 'toplam_tiklama', 50, 'bakiye', 200),
            (2, 'Büyüme Atağı', '10 taraftar kazan', 'taraftar_kazanimi', 10, 'taraftar', 15),
            (3, 'Yatırım Zamanı', '2 eşya satın al', 'esya_satin_alma', 2, 'bakiye', 300),
        ]
        cursor.executemany('INSERT INTO daily_quests (id, name, description, condition_type, condition_value, reward_type, reward_amount) VALUES (%s, %s, %s, %s, %s, %s, %s)', gorevler)

    cursor.execute('SELECT COUNT(*) FROM loot_boxes')
    if cursor.fetchone()[0] == 0:
        bronz_pool = json.dumps([
            {'tip': 'bakiye', 'miktar': 50, 'agirlik': 40},
            {'tip': 'bakiye', 'miktar': 100, 'agirlik': 30},
            {'tip': 'taraftar', 'miktar': 5, 'agirlik': 20},
            {'tip': 'tiklamaGucu', 'miktar': 1, 'agirlik': 10},
        ])
        gumus_pool = json.dumps([
            {'tip': 'bakiye', 'miktar': 200, 'agirlik': 30},
            {'tip': 'bakiye', 'miktar': 500, 'agirlik': 25},
            {'tip': 'taraftar', 'miktar': 20, 'agirlik': 25},
            {'tip': 'tiklamaGucu', 'miktar': 3, 'agirlik': 20},
        ])
        altin_pool = json.dumps([
            {'tip': 'bakiye', 'miktar': 1000, 'agirlik': 30},
            {'tip': 'bakiye', 'miktar': 2500, 'agirlik': 25},
            {'tip': 'taraftar', 'miktar': 100, 'agirlik': 25},
            {'tip': 'tiklamaGucu', 'miktar': 10, 'agirlik': 20},
        ])
        cursor.execute('INSERT INTO loot_boxes (id, name, reward_pool) VALUES (%s, %s)', (1, bronz_pool))
        cursor.execute('INSERT INTO loot_boxes (id, name, reward_pool) VALUES (%s, %s)', (2, gumus_pool))
        cursor.execute('INSERT INTO loot_boxes (id, name, reward_pool) VALUES (%s, %s)', (3, altin_pool))

    cursor.execute('SELECT COUNT(*) FROM prestige_special_items')
    if cursor.fetchone()[0] == 0:
        ozel_esyalar = [
            (1, 'Efsanevi Mikrofon', 'Prestij 1 ile açılır, tıklama gücü +5', '🎤', 1, 'tiklamaGucu', 5),
            (2, 'Altın Yayın Koltuğu', 'Prestij 2 ile açılır, pasif gelir +50₺/sn', '🪑', 2, 'saniyeGeliri', 50),
            (3, 'Gökkuşağı Işıkları', 'Prestij 3 ile açılır, tüm gelir çarpanı +0.2', '🌈', 3, 'carpan', 0.2),
            (4, 'Platin Sponsor', 'Prestij 5 ile açılır, taraftar kazanımı +2/sn', '💼', 5, 'taraftar_kazanimi', 2),
        ]
        cursor.executemany('INSERT INTO prestige_special_items (id, name, description, icon, required_prestige, bonus_type, bonus_value) VALUES (%s, %s, %s, %s, %s, %s, %s)', ozel_esyalar)

    cursor.execute('SELECT COUNT(*) FROM ai_opponents')
    if cursor.fetchone()[0] == 0:
        rakipler = [
            (1, 'Yayıncı Ali', '👨‍💻', 50, 100, 1, 1.02, datetime.now()),
            (2, 'Streamer Ayşe', '👩‍💻', 120, 300, 2, 1.03, datetime.now()),
            (3, 'Gamer Mehmet', '🧑‍💻', 300, 800, 3, 1.05, datetime.now()),
            (4, 'Elit Yayıncı', '👑', 1000, 2500, 5, 1.08, datetime.now()),
        ]
        cursor.executemany('INSERT INTO ai_opponents (id, name, icon, income, followers, level, growth_rate, last_updated) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', rakipler)

    cursor.execute('SELECT COUNT(*) FROM studio_decorations')
    if cursor.fetchone()[0] == 0:
        dekorlar = [
            (1, 'Modern Masa', 'Şık bir yayın masası', '🪑', 500, 'tiklama_carpan', 0.05, False, 0),
            (2, 'RGB Işıklar', 'Renkli ışıklandırma', '💡', 1200, 'gelir_carpan', 0.1, False, 0),
            (3, 'Ses Yalıtım Paneli', 'Ses kalitesini artırır', '🧱', 2000, 'taraftar_carpan', 0.1, False, 0),
            (4, 'Altın Mikrofon', 'Lüks görünüm', '🎙️', 5000, 'tiklama_carpan', 0.2, True, 1),
            (5, 'Projektör', 'Görsel efektler', '📽️', 8000, 'gelir_carpan', 0.25, True, 2),
        ]
        cursor.executemany('INSERT INTO studio_decorations (id, name, description, icon, price, bonus_type, bonus_value, is_special, required_prestige) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)', dekorlar)

    cursor.execute('SELECT COUNT(*) FROM etkinlikler')
    if cursor.fetchone()[0] == 0:
        simdi = datetime.now()
        bir_hafta_sonra = simdi + timedelta(days=7)
        etkinlikler = [
            (1, '🎯 Haftanın Yayıncısı', 'Bu hafta toplam 1000 tıklama yap!', simdi, bir_hafta_sonra, 'bakiye', 1000),
            (2, '📈 Büyüme Haftası', 'Bu hafta 500 taraftar kazan!', simdi, bir_hafta_sonra, 'taraftar', 100),
            (3, '💰 Altın Hafta', 'Bu hafta toplam 10000₺ kazan!', simdi, bir_hafta_sonra, 'tiklamaGucu', 5),
        ]
        cursor.executemany('INSERT INTO etkinlikler (id, name, description, baslangic, bitis, reward_type, reward_amount) VALUES (%s, %s, %s, %s, %s, %s, %s)', etkinlikler)

    conn.commit()
    conn.close()

veritabani_kur()

# ---------- FORMAT PARA ----------
def format_para(sayi):
    if sayi >= 1e9: return f"{sayi/1e9:.1f}B"
    if sayi >= 1e6: return f"{sayi/1e6:.1f}M"
    if sayi >= 1e3: return f"{sayi/1e3:.1f}K"
    return str(int(sayi))

# ---------- LOGIN DECORATOR ----------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ---------- YARDIMCI FONKSİYONLAR ----------
def get_or_create_user(username):
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
    row = cursor.fetchone()
    if row:
        user_id = row[0]
    else:
        cursor.execute('INSERT INTO users (username) VALUES (%s) RETURNING id', (username,))
        user_id = cursor.fetchone()[0]
        default_market = {
            "enerji": {"fiyat": 75, "tur": "tiklama", "guc": 2, "fiyatArtisi": 1.5, "gerekenTaraftar": 0},
            "mouse": {"fiyat": 150, "tur": "tiklama", "guc": 3, "fiyatArtisi": 1.6, "gerekenTaraftar": 0},
            "kamera": {"fiyat": 500, "tur": "tiklama", "guc": 8, "fiyatArtisi": 1.7, "gerekenTaraftar": 0},
            "klavye": {"fiyat": 1200, "tur": "tiklama", "guc": 15, "fiyatArtisi": 1.8, "gerekenTaraftar": 0},
            "amator": {"fiyat": 300, "tur": "pasif", "guc": 3, "fiyatArtisi": 1.5, "gerekenTaraftar": 0},
            "yesilekran": {"fiyat": 800, "tur": "pasif", "guc": 10, "fiyatArtisi": 1.6, "gerekenTaraftar": 50},
            "yildiz": {"fiyat": 2000, "tur": "pasif", "guc": 20, "fiyatArtisi": 1.7, "gerekenTaraftar": 0},
            "moderator": {"fiyat": 4500, "tur": "pasif", "guc": 40, "fiyatArtisi": 1.8, "gerekenTaraftar": 100},
            "reklam": {"fiyat": 10000, "tur": "pasif", "guc": 80, "fiyatArtisi": 1.9, "gerekenTaraftar": 150},
            "yayinevi": {"fiyat": 25000, "tur": "pasif", "guc": 200, "fiyatArtisi": 2.0, "gerekenTaraftar": 300},
            "espor": {"fiyat": 60000, "tur": "pasif", "guc": 500, "fiyatArtisi": 2.1, "gerekenTaraftar": 500},
            "globalturnuva": {"fiyat": 150000, "tur": "pasif", "guc": 1200, "fiyatArtisi": 2.2, "gerekenTaraftar": 1000}
        }
        default_personeller = {
            "sosyal_medyaci": {"fiyat": 15000, "alinma": 0, "gerekenTaraftar": 200},
            "vergi_uzmani": {"fiyat": 50000, "alinma": 0, "gerekenTaraftar": 600},
            "kurgucu": {"fiyat": 120000, "alinma": 0, "gerekenTaraftar": 1500}
        }
        cursor.execute('''INSERT INTO oyun_kaydi 
            (user_id, bakiye, taraftar, tiklamaGucu, saniyeGeliri, marketEsyalari, level, xp, mesajlar, alinan_oduller, prestij, personeller, toplam_tiklama, son_giris, gunluk_odul_alinmis) 
            VALUES (%s, 0, 0, 1, 0, %s, 1, 0, %s, %s, 0, %s, 0, %s, FALSE)''',
            (user_id, json.dumps(default_market), json.dumps([]), json.dumps([]), json.dumps(default_personeller), datetime.now()))
        cursor.execute('INSERT INTO yayin_istatistikleri (user_id) VALUES (%s)', (user_id,))
        cursor.execute('INSERT INTO liderlik (user_id) VALUES (%s)', (user_id,))
        conn.commit()
    conn.close()
    return user_id

# ---------- AUTH ROUTES ----------
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if not username:
            flash('Kullanıcı adı boş olamaz.', 'danger')
            return render_template('index.html', show_login=True)
        user_id = get_or_create_user(username)
        session['user_id'] = user_id
        session['username'] = username
        return redirect(url_for('ana_ekran'))
    return render_template('index.html', show_login=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def ana_ekran():
    return render_template('index.html', show_login=False)

# ---------- OYUN ENDPOINT'LERİ ----------
@app.route('/kaydet', methods=['POST'])
@login_required
def oyunu_kaydet():
    try:
        data = request.json
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = SmartCursor(conn)
        cursor.execute('''UPDATE oyun_kaydi SET 
            bakiye=%s, taraftar=%s, tiklamaGucu=%s, saniyeGeliri=%s, 
            marketEsyalari=%s, level=%s, xp=%s, mesajlar=%s, 
            alinan_oduller=%s, prestij=%s, personeller=%s, toplam_tiklama=%s
            WHERE user_id=%s''',
            (data['bakiye'], data['taraftar'], data['tiklamaGucu'], data['saniyeGeliri'],
             json.dumps(data['marketEsyalari']), data['level'], data['xp'],
             json.dumps(data['mesajlar']), json.dumps(data.get('alinanOduller', [])),
             data.get('prestij', 0), json.dumps(data.get('personeller', {})),
             data.get('toplamTiklama', 0), user_id))
        conn.commit()
        conn.close()
        return jsonify({"durum": "basarili"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

@app.route('/yukle', methods=['GET'])
@login_required
def oyunu_yukle():
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = SmartCursor(conn)
        cursor.execute('''SELECT bakiye, taraftar, tiklamaGucu, saniyeGeliri, marketEsyalari, level, xp, mesajlar, alinan_oduller, prestij, personeller, toplam_tiklama, son_giris, gunluk_odul_alinmis 
                         FROM oyun_kaydi WHERE user_id=%s''', (user_id,))
        satir = cursor.fetchone()
        conn.close()
        if satir:
            return jsonify({
                "bakiye": satir[0],
                "taraftar": satir[1],
                "tiklamaGucu": satir[2],
                "saniyeGeliri": satir[3],
                "marketEsyalari": json.loads(satir[4]),
                "level": satir[5],
                "xp": satir[6],
                "mesajlar": json.loads(satir[7]) if satir[7] else [],
                "alinanOduller": json.loads(satir[8]) if satir[8] else [],
                "prestij": satir[9] if satir[9] else 0,
                "personeller": json.loads(satir[10]) if satir[10] else {},
                "toplamTiklama": satir[11] if satir[11] else 0,
                "son_giris": satir[12],
                "gunluk_odul_alinmis": bool(satir[13]) if satir[13] else False
            })
        return jsonify({"durum": "yok"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

# Diğer tüm endpoint'ler (prestij_yap, teklif_al, teklif_islem, gunluk_odul, gunluk_odul_al, istatistikler, etkinlikler, etkinlik_progress, etkinlik_tamamla, liderlik, achievements, daily_quests, claim_daily_quest, studio_decorations, buy_decoration, equip_decoration, open_lootbox, prestige_special_items, ai_opponents, challenge_ai) aynen kalır, sadece current_user.id yerine session['user_id'] kullanılır. Kısalık için hepsini buraya yazmıyorum ama kullandığın dosyada hepsi mevcut olmalı.

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)