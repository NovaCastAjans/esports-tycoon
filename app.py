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

# ---------- SMART CURSOR ----------
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
        # Düzeltme: 3 sütun için 3 değer
        cursor.execute('INSERT INTO loot_boxes (id, name, reward_pool) VALUES (%s, %s, %s)', (1, 'Bronz Kutu', bronz_pool))
        cursor.execute('INSERT INTO loot_boxes (id, name, reward_pool) VALUES (%s, %s, %s)', (2, 'Gümüş Kutu', gumus_pool))
        cursor.execute('INSERT INTO loot_boxes (id, name, reward_pool) VALUES (%s, %s, %s)', (3, 'Altın Kutu', altin_pool))

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

@app.route('/prestij_yap', methods=['POST'])
@login_required
def prestij_islem():
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = SmartCursor(conn)
        cursor.execute('SELECT prestij FROM oyun_kaydi WHERE user_id=%s', (user_id,))
        mevcut_prestij = cursor.fetchone()[0]
        yeni_prestij = mevcut_prestij + 1
        default_market = {"enerji": {"fiyat": 75, "tur": "tiklama", "guc": 2, "fiyatArtisi": 1.5, "gerekenTaraftar": 0}, "mouse": {"fiyat": 150, "tur": "tiklama", "guc": 3, "fiyatArtisi": 1.6, "gerekenTaraftar": 0}, "kamera": {"fiyat": 500, "tur": "tiklama", "guc": 8, "fiyatArtisi": 1.7, "gerekenTaraftar": 0}, "klavye": {"fiyat": 1200, "tur": "tiklama", "guc": 15, "fiyatArtisi": 1.8, "gerekenTaraftar": 0}, "amator": {"fiyat": 300, "tur": "pasif", "guc": 3, "fiyatArtisi": 1.5, "gerekenTaraftar": 0}, "yesilekran": {"fiyat": 800, "tur": "pasif", "guc": 10, "fiyatArtisi": 1.6, "gerekenTaraftar": 50}, "yildiz": {"fiyat": 2000, "tur": "pasif", "guc": 20, "fiyatArtisi": 1.7, "gerekenTaraftar": 0}, "moderator": {"fiyat": 4500, "tur": "pasif", "guc": 40, "fiyatArtisi": 1.8, "gerekenTaraftar": 100}, "reklam": {"fiyat": 10000, "tur": "pasif", "guc": 80, "fiyatArtisi": 1.9, "gerekenTaraftar": 150}, "yayinevi": {"fiyat": 25000, "tur": "pasif", "guc": 200, "fiyatArtisi": 2.0, "gerekenTaraftar": 300}, "espor": {"fiyat": 60000, "tur": "pasif", "guc": 500, "fiyatArtisi": 2.1, "gerekenTaraftar": 500}, "globalturnuva": {"fiyat": 150000, "tur": "pasif", "guc": 1200, "fiyatArtisi": 2.2, "gerekenTaraftar": 1000}}
        default_personeller = {"sosyal_medyaci": {"fiyat": 15000, "alinma": 0, "gerekenTaraftar": 200}, "vergi_uzmani": {"fiyat": 50000, "alinma": 0, "gerekenTaraftar": 600}, "kurgucu": {"fiyat": 120000, "alinma": 0, "gerekenTaraftar": 1500}}
        cursor.execute('''UPDATE oyun_kaydi SET 
            bakiye=0, taraftar=0, tiklamaGucu=1, saniyeGeliri=0, 
            marketEsyalari=%s, level=1, xp=0, mesajlar=%s, 
            alinan_oduller=%s, prestij=%s, personeller=%s, toplam_tiklama=0
            WHERE user_id=%s''',
            (json.dumps(default_market), json.dumps([]), json.dumps([]), yeni_prestij, json.dumps(default_personeller), user_id))
        cursor.execute('UPDATE yayin_istatistikleri SET toplam_yayin_suresi=0, toplam_kazanilan_para=0, toplam_kazanilan_taraftar=0, toplam_tiklama=0, en_yuksek_gelir=0 WHERE user_id=%s', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({"durum": "basarili"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

@app.route('/teklif_al', methods=['POST'])
@login_required
def teklif_al():
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = SmartCursor(conn)
        cursor.execute('SELECT saniyeGeliri, level, prestij, mesajlar FROM oyun_kaydi WHERE user_id=%s', (user_id,))
        satir = cursor.fetchone()
        saniye_geliri = satir[0] if satir[0] > 0 else 10
        level = satir[1]
        prestij = satir[2]
        mesajlar = json.loads(satir[3]) if satir[3] else []
        if len(mesajlar) > 0:
            conn.close()
            return jsonify({"durum": "bekle"})
        temel_kazanc = saniye_geliri * 30
        seviye_bonusu = 1.0 + (level * 0.03)
        carpan = seviye_bonusu * (1.0 + prestij * 0.2)
        temel_bakiye = int(temel_kazanc * carpan)
        temel_taraftar = int(5 + (level * 1.5) * (1.0 + (prestij*0.3)))
        teklif_turleri = [
            {"tip": "yatirim", "baslik": "🎁 Çekiliş", "metin": f"{format_para(temel_bakiye * 0.6)}₺ harcayıp {int(temel_taraftar * 2)} taraftar kazan.", "m_bakiye": int(temel_bakiye * 0.6), "m_taraftar": 0, "k_bakiye": 0, "k_taraftar": int(temel_taraftar * 2)},
            {"tip": "agresif", "baslik": "📺 Reklam", "metin": f"{int(temel_taraftar * 0.8)} taraftar kaybedip {format_para(temel_bakiye * 2)}₺ kazan.", "m_bakiye": 0, "m_taraftar": int(temel_taraftar * 0.8), "k_bakiye": int(temel_bakiye * 2), "k_taraftar": 0},
            {"tip": "turnuva", "baslik": "🏆 Turnuva", "metin": f"{format_para(temel_bakiye * 0.4)}₺ yatır, kazanırsan {format_para(temel_bakiye * 1.2)}₺ ve {temel_taraftar} taraftar.", "m_bakiye": int(temel_bakiye * 0.4), "m_taraftar": 0, "k_bakiye": int(temel_bakiye * 1.2), "k_taraftar": temel_taraftar},
            {"tip": "sponsor", "baslik": "🤝 Sponsor", "metin": f"{format_para(temel_bakiye * 0.8)}₺ ve {int(temel_taraftar * 0.5)} taraftar kazan.", "m_bakiye": 0, "m_taraftar": 0, "k_bakiye": int(temel_bakiye * 0.8), "k_taraftar": int(temel_taraftar * 0.5)}
        ]
        secilen = random.choice(teklif_turleri)
        mesajlar.append({
            "id": random.randint(10000, 99999),
            "baslik": secilen["baslik"],
            "metin": secilen["metin"],
            "maliyet_bakiye": secilen["m_bakiye"],
            "maliyet_taraftar": secilen["m_taraftar"],
            "kazanc_bakiye": secilen["k_bakiye"],
            "kazanc_taraftar": secilen["k_taraftar"]
        })
        cursor.execute('UPDATE oyun_kaydi SET mesajlar=%s WHERE user_id=%s', (json.dumps(mesajlar), user_id))
        conn.commit()
        conn.close()
        return jsonify({"durum": "basarili"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

@app.route('/teklif_islem', methods=['POST'])
@login_required
def teklif_islem():
    try:
        data = request.json
        islem_id = data.get('id')
        aksiyon = data.get('aksiyon')
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = SmartCursor(conn)
        cursor.execute('SELECT bakiye, taraftar, mesajlar FROM oyun_kaydi WHERE user_id=%s', (user_id,))
        satir = cursor.fetchone()
        bakiye, taraftar, mesajlar = satir[0], satir[1], json.loads(satir[2]) if satir[2] else []
        teklif = next((m for m in mesajlar if m.get('id') == islem_id), None)
        if teklif and aksiyon == 'kabul':
            if bakiye < teklif.get('maliyet_bakiye', 0):
                conn.close()
                return jsonify({"durum": "hata", "mesaj": "Bakiye yetersiz!"})
            if taraftar < teklif.get('maliyet_taraftar', 0):
                conn.close()
                return jsonify({"durum": "hata", "mesaj": "Taraftar yetersiz!"})
            bakiye -= teklif.get('maliyet_bakiye', 0)
            taraftar -= teklif.get('maliyet_taraftar', 0)
            bakiye += teklif.get('kazanc_bakiye', 0)
            taraftar += teklif.get('kazanc_taraftar', 0)
        mesajlar = [m for m in mesajlar if m.get('id') != islem_id]
        cursor.execute('UPDATE oyun_kaydi SET bakiye=%s, taraftar=%s, mesajlar=%s WHERE user_id=%s', (bakiye, taraftar, json.dumps(mesajlar), user_id))
        conn.commit()
        conn.close()
        return jsonify({"durum": "basarili"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 500

@app.route('/gunluk_odul', methods=['GET'])
@login_required
def gunluk_odul():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT son_giris, gunluk_odul_alinmis FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    son_giris, alinmis = cursor.fetchone()
    son_giris = datetime.fromisoformat(son_giris) if son_giris else datetime.now()
    bugun = datetime.now().date()
    conn.close()
    if son_giris.date() != bugun and not alinmis:
        return jsonify({"durum": "alabilir", "mesaj": "Günlük giriş ödülünü alabilirsin!"})
    elif son_giris.date() == bugun and not alinmis:
        return jsonify({"durum": "alabilir", "mesaj": "Günlük giriş ödülünü al!"})
    else:
        return jsonify({"durum": "alinmis", "mesaj": "Bugün ödülünü zaten aldın."})

@app.route('/gunluk_odul_al', methods=['POST'])
@login_required
def gunluk_odul_al():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT gunluk_odul_alinmis FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    alinmis = cursor.fetchone()[0]
    if alinmis:
        conn.close()
        return jsonify({"durum": "hata", "mesaj": "Zaten aldın!"})
    odul_bakiye = 100 + random.randint(0, 50)
    odul_taraftar = 10 + random.randint(0, 10)
    cursor.execute('UPDATE oyun_kaydi SET bakiye = bakiye + %s, taraftar = taraftar + %s, son_giris = %s, gunluk_odul_alinmis = TRUE WHERE user_id=%s',
                   (odul_bakiye, odul_taraftar, datetime.now(), user_id))
    cursor.execute('UPDATE yayin_istatistikleri SET toplam_kazanilan_para = toplam_kazanilan_para + %s, toplam_kazanilan_taraftar = toplam_kazanilan_taraftar + %s WHERE user_id=%s',
                   (odul_bakiye, odul_taraftar, user_id))
    conn.commit()
    conn.close()
    return jsonify({"durum": "basarili", "odul_bakiye": odul_bakiye, "odul_taraftar": odul_taraftar})

@app.route('/istatistikler', methods=['GET'])
@login_required
def istatistikler():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT toplam_yayin_suresi, toplam_kazanilan_para, toplam_kazanilan_taraftar, toplam_tiklama, en_yuksek_gelir FROM yayin_istatistikleri WHERE user_id=%s', (user_id,))
    istatistik = cursor.fetchone()
    conn.close()
    if istatistik:
        return jsonify({
            "toplam_yayin_suresi": istatistik[0],
            "toplam_kazanilan_para": istatistik[1],
            "toplam_kazanilan_taraftar": istatistik[2],
            "toplam_tiklama": istatistik[3],
            "en_yuksek_gelir": istatistik[4]
        })
    return jsonify({"durum": "yok"})

@app.route('/etkinlikler', methods=['GET'])
@login_required
def etkinlikler_listesi():
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    simdi = datetime.now()
    cursor.execute('SELECT id, name, description, baslangic, bitis, reward_type, reward_amount FROM etkinlikler WHERE aktif=TRUE')
    etkinlikler = cursor.fetchall()
    sonuc = []
    for e in etkinlikler:
        baslangic = datetime.fromisoformat(e[3])
        bitis = datetime.fromisoformat(e[4])
        if baslangic <= simdi <= bitis:
            sonuc.append({
                'id': e[0], 'name': e[1], 'description': e[2],
                'baslangic': e[3], 'bitis': e[4],
                'reward_type': e[5], 'reward_amount': e[6],
                'aktif': True
            })
    conn.close()
    return jsonify(sonuc)

@app.route('/etkinlik_progress', methods=['GET'])
@login_required
def etkinlik_progress():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT etkinlik_id, progress, tamamlandi FROM kullanici_etkinlik_progress WHERE user_id=%s', (user_id,))
    progress = cursor.fetchall()
    conn.close()
    return jsonify([{'etkinlik_id': p[0], 'progress': p[1], 'tamamlandi': bool(p[2])} for p in progress])

@app.route('/etkinlik_tamamla', methods=['POST'])
@login_required
def etkinlik_tamamla():
    data = request.json
    etkinlik_id = data.get('etkinlik_id')
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT reward_type, reward_amount FROM etkinlikler WHERE id=%s AND aktif=TRUE', (etkinlik_id,))
    etkinlik = cursor.fetchone()
    if not etkinlik:
        conn.close()
        return jsonify({"durum": "hata", "mesaj": "Etkinlik bulunamadı"})
    cursor.execute('SELECT tamamlandi FROM kullanici_etkinlik_progress WHERE user_id=%s AND etkinlik_id=%s', (user_id, etkinlik_id))
    satir = cursor.fetchone()
    if satir and satir[0]:
        conn.close()
        return jsonify({"durum": "hata", "mesaj": "Zaten tamamlanmış"})
    cursor.execute('SELECT bakiye, taraftar, tiklamaGucu FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu = cursor.fetchone()
    bakiye, taraftar, tiklamaGucu = oyuncu
    if etkinlik[0] == 'bakiye':
        bakiye += etkinlik[1]
    elif etkinlik[0] == 'taraftar':
        taraftar += etkinlik[1]
    elif etkinlik[0] == 'tiklamaGucu':
        tiklamaGucu += etkinlik[1]
    cursor.execute('UPDATE oyun_kaydi SET bakiye=%s, taraftar=%s, tiklamaGucu=%s WHERE user_id=%s', (bakiye, taraftar, tiklamaGucu, user_id))
    cursor.execute('INSERT INTO kullanici_etkinlik_progress (user_id, etkinlik_id, progress, tamamlandi) VALUES (%s, %s, %s, TRUE) ON CONFLICT (user_id, etkinlik_id) DO UPDATE SET tamamlandi=TRUE', (user_id, etkinlik_id, etkinlik[1]))
    conn.commit()
    conn.close()
    return jsonify({"durum": "basarili", "reward_type": etkinlik[0], "reward_amount": etkinlik[1]})

@app.route('/liderlik', methods=['GET'])
@login_required
def liderlik():
    user_id = session['user_id']
    username = session['username']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT prestij, level, toplam_gelir, toplam_taraftar FROM liderlik WHERE user_id=%s', (user_id,))
    lider = cursor.fetchone()
    conn.close()
    if lider:
        return jsonify([{
            'sira': 1,
            'kullanici': username,
            'prestij': lider[0],
            'level': lider[1],
            'toplam_gelir': lider[2],
            'toplam_taraftar': lider[3]
        }])
    return jsonify([])

@app.route('/achievements', methods=['GET'])
@login_required
def achievements():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT toplam_tiklama, taraftar, saniyeGeliri, level, prestij FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu = cursor.fetchone()
    cursor.execute('SELECT id, name, description, icon, condition_type, condition_value, reward_type, reward_amount FROM achievements')
    tum_basarimlar = cursor.fetchall()
    sonuc = []
    for b in tum_basarimlar:
        unlocked = False
        if b[4] == 'toplam_tiklama' and oyuncu[0] >= b[5]:
            unlocked = True
        elif b[4] == 'taraftar_sayisi' and oyuncu[1] >= b[5]:
            unlocked = True
        elif b[4] == 'saniye_geliri' and oyuncu[2] >= b[5]:
            unlocked = True
        elif b[4] == 'level' and oyuncu[3] >= b[5]:
            unlocked = True
        elif b[4] == 'prestij_sayisi' and oyuncu[4] >= b[5]:
            unlocked = True
        sonuc.append({
            'id': b[0], 'name': b[1], 'description': b[2], 'icon': b[3],
            'condition_type': b[4], 'condition_value': b[5],
            'reward_type': b[6], 'reward_amount': b[7],
            'unlocked': unlocked
        })
    conn.close()
    return jsonify(sonuc)

@app.route('/daily_quests', methods=['GET'])
@login_required
def daily_quests():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT id, name, description, condition_type, condition_value, reward_type, reward_amount FROM daily_quests')
    gorevler = cursor.fetchall()
    cursor.execute('SELECT toplam_tiklama, taraftar FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu = cursor.fetchone()
    sonuc = []
    for g in gorevler:
        progress = 0
        if g[3] == 'toplam_tiklama':
            progress = oyuncu[0]
        elif g[3] == 'taraftar_kazanimi':
            progress = oyuncu[1]
        elif g[3] == 'esya_satin_alma':
            progress = 0
        completed = progress >= g[4]
        sonuc.append({
            'id': g[0], 'name': g[1], 'description': g[2],
            'condition_type': g[3], 'condition_value': g[4],
            'reward_type': g[5], 'reward_amount': g[6],
            'progress': progress, 'completed': completed
        })
    conn.close()
    return jsonify(sonuc)

@app.route('/claim_daily_quest', methods=['POST'])
@login_required
def claim_daily_quest():
    data = request.json
    quest_id = data.get('quest_id')
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT reward_type, reward_amount, condition_type, condition_value FROM daily_quests WHERE id=%s', (quest_id,))
    gorev = cursor.fetchone()
    if not gorev:
        conn.close()
        return jsonify({'durum': 'hata', 'mesaj': 'Geçersiz görev'})
    cursor.execute('SELECT toplam_tiklama, taraftar FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu = cursor.fetchone()
    progress = 0
    if gorev[2] == 'toplam_tiklama':
        progress = oyuncu[0]
    elif gorev[2] == 'taraftar_kazanimi':
        progress = oyuncu[1]
    elif gorev[2] == 'esya_satin_alma':
        progress = 0
    if progress < gorev[3]:
        conn.close()
        return jsonify({'durum': 'hata', 'mesaj': 'Görev henüz tamamlanmamış!'})
    cursor.execute('SELECT bakiye, taraftar, tiklamaGucu FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu2 = cursor.fetchone()
    bakiye, taraftar, tiklamaGucu = oyuncu2
    if gorev[0] == 'bakiye':
        bakiye += gorev[1]
    elif gorev[0] == 'taraftar':
        taraftar += gorev[1]
    elif gorev[0] == 'tiklamaGucu':
        tiklamaGucu += gorev[1]
    cursor.execute('UPDATE oyun_kaydi SET bakiye=%s, taraftar=%s, tiklamaGucu=%s WHERE user_id=%s', (bakiye, taraftar, tiklamaGucu, user_id))
    bugun = datetime.now().date()
    cursor.execute('INSERT INTO daily_quest_progress (user_id, quest_id, progress, completed, date) VALUES (%s, %s, %s, TRUE, %s) ON CONFLICT (user_id, quest_id, date) DO UPDATE SET progress=%s, completed=TRUE', (user_id, quest_id, progress, bugun, progress))
    conn.commit()
    conn.close()
    return jsonify({'durum': 'basarili'})

@app.route('/studio_decorations', methods=['GET'])
@login_required
def studio_decorations():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT id, name, description, icon, price, bonus_type, bonus_value, is_special, required_prestige FROM studio_decorations')
    dekorlar = cursor.fetchall()
    cursor.execute('SELECT decoration_id, equipped FROM user_decorations WHERE user_id=%s', (user_id,))
    sahip_olanlar = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    sonuc = []
    for d in dekorlar:
        sonuc.append({
            'id': d[0], 'name': d[1], 'description': d[2], 'icon': d[3],
            'price': d[4], 'bonus_type': d[5], 'bonus_value': d[6],
            'is_special': bool(d[7]), 'required_prestige': d[8],
            'owned': d[0] in sahip_olanlar,
            'equipped': sahip_olanlar.get(d[0], False)
        })
    return jsonify(sonuc)

@app.route('/buy_decoration', methods=['POST'])
@login_required
def buy_decoration():
    data = request.json
    deco_id = data.get('decoration_id')
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT price, is_special, required_prestige FROM studio_decorations WHERE id=%s', (deco_id,))
    dekor = cursor.fetchone()
    if not dekor:
        conn.close()
        return jsonify({'durum': 'hata', 'mesaj': 'Dekorasyon bulunamadı'})
    if dekor[1]:
        cursor.execute('SELECT prestij FROM oyun_kaydi WHERE user_id=%s', (user_id,))
        prestij = cursor.fetchone()[0]
        if prestij < dekor[2]:
            conn.close()
            return jsonify({'durum': 'hata', 'mesaj': 'Bu dekorasyon için yeterli prestij seviyesine sahip değilsin'})
    cursor.execute('SELECT bakiye FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    bakiye = cursor.fetchone()[0]
    if bakiye < dekor[0]:
        conn.close()
        return jsonify({'durum': 'hata', 'mesaj': 'Yetersiz bakiye'})
    cursor.execute('UPDATE oyun_kaydi SET bakiye = bakiye - %s WHERE user_id=%s', (dekor[0], user_id))
    cursor.execute('INSERT INTO user_decorations (user_id, decoration_id, purchased_at, equipped) VALUES (%s, %s, %s, FALSE)', (user_id, deco_id, datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({'durum': 'basarili'})

@app.route('/equip_decoration', methods=['POST'])
@login_required
def equip_decoration():
    data = request.json
    deco_id = data.get('decoration_id')
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('UPDATE user_decorations SET equipped = FALSE WHERE user_id=%s', (user_id,))
    cursor.execute('UPDATE user_decorations SET equipped = TRUE WHERE user_id=%s AND decoration_id=%s', (user_id, deco_id))
    conn.commit()
    conn.close()
    return jsonify({'durum': 'basarili'})

@app.route('/open_lootbox', methods=['POST'])
@login_required
def open_lootbox():
    data = request.json
    box_id = data.get('box_id')
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT reward_pool FROM loot_boxes WHERE id=%s', (box_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'durum': 'hata', 'mesaj': 'Geçersiz kutu'})
    pool = json.loads(result[0])
    toplam_agirlik = sum(item['agirlik'] for item in pool)
    r = random.randint(1, toplam_agirlik)
    secilen = None
    for item in pool:
        r -= item['agirlik']
        if r <= 0:
            secilen = item
            break
    if not secilen:
        secilen = pool[-1]
    cursor.execute('SELECT bakiye, taraftar, tiklamaGucu FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu = cursor.fetchone()
    bakiye, taraftar, tiklamaGucu = oyuncu
    if secilen['tip'] == 'bakiye':
        bakiye += secilen['miktar']
    elif secilen['tip'] == 'taraftar':
        taraftar += secilen['miktar']
    elif secilen['tip'] == 'tiklamaGucu':
        tiklamaGucu += secilen['miktar']
    cursor.execute('UPDATE oyun_kaydi SET bakiye=%s, taraftar=%s, tiklamaGucu=%s WHERE user_id=%s', (bakiye, taraftar, tiklamaGucu, user_id))
    cursor.execute('INSERT INTO user_loot_history (user_id, loot_id, reward_type, reward_amount, opened_at) VALUES (%s, %s, %s, %s, %s)', (user_id, box_id, secilen['tip'], secilen['miktar'], datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({'durum': 'basarili', 'reward_type': secilen['tip'], 'reward_amount': secilen['miktar']})

@app.route('/prestige_special_items', methods=['GET'])
@login_required
def prestige_special_items():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT prestij FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    prestij = cursor.fetchone()[0]
    cursor.execute('SELECT id, name, description, icon, required_prestige, bonus_type, bonus_value FROM prestige_special_items WHERE required_prestige <= %s', (prestij,))
    items = cursor.fetchall()
    conn.close()
    return jsonify([{
        'id': i[0], 'name': i[1], 'description': i[2], 'icon': i[3],
        'required_prestige': i[4], 'bonus_type': i[5], 'bonus_value': i[6]
    } for i in items])

@app.route('/ai_opponents', methods=['GET'])
@login_required
def ai_opponents():
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    rakipler = cursor.execute('SELECT id, income, followers, level, growth_rate, last_updated FROM ai_opponents').fetchall()
    simdi = datetime.now()
    for r in rakipler:
        fark = (simdi - r[5]).total_seconds() / 3600
        if fark > 1:
            yeni_gelir = int(r[1] * (r[4] ** fark))
            yeni_taraftar = int(r[2] * (r[4] ** (fark * 0.5)))
            cursor.execute('UPDATE ai_opponents SET income=%s, followers=%s, last_updated=%s WHERE id=%s', (yeni_gelir, yeni_taraftar, simdi, r[0]))
    conn.commit()
    cursor.execute('SELECT id, name, icon, income, followers, level FROM ai_opponents')
    rakipler = cursor.fetchall()
    conn.close()
    return jsonify([{
        'id': r[0], 'name': r[1], 'icon': r[2],
        'income': r[3], 'followers': r[4], 'level': r[5]
    } for r in rakipler])

@app.route('/challenge_ai', methods=['POST'])
@login_required
def challenge_ai():
    data = request.json
    ai_id = data.get('ai_id')
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = SmartCursor(conn)
    cursor.execute('SELECT income, followers FROM ai_opponents WHERE id=%s', (ai_id,))
    rakip = cursor.fetchone()
    cursor.execute('SELECT bakiye, taraftar, saniyeGeliri FROM oyun_kaydi WHERE user_id=%s', (user_id,))
    oyuncu = cursor.fetchone()
    oyuncu_puan = oyuncu[2] * 2 + oyuncu[1]
    rakip_puan = rakip[0] * 2 + rakip[1]
    if oyuncu_puan > rakip_puan:
        odul = random.randint(100, 500)
        cursor.execute('UPDATE oyun_kaydi SET bakiye = bakiye + %s WHERE user_id=%s', (odul, user_id))
        conn.commit()
        conn.close()
        return jsonify({'durum': 'kazandi', 'odul': odul})
    else:
        conn.close()
        return jsonify({'durum': 'kaybetti', 'mesaj': 'Rakip senden daha güçlü!'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)