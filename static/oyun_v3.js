console.log("Oyun v3 motoru aktif!");

// Global Değişkenler
let bakiye = 0, taraftar = 0, tiklamaGucu = 1, saniyeGeliri = 0, level = 1, xp = 0, xpGereken = 100;
let mesajlar = [], alinanOduller = [], marketEsyalari = {}, personeller = {}, prestij = 0;
let pasifInterval = null;
let toplamTiklama = 0;
let istatistikler = {};
let gunlukOdulAlinmis = false;

// ---------- SES SİSTEMİ ----------
let sesAktif = true;
let arkaPlanMuzik = null;

function sesOynat(dosya) {
    if (!sesAktif) return;
    try {
        const ses = new Audio('/static/sounds/' + dosya);
        ses.volume = 0.3;
        ses.play().catch(() => {});
    } catch (e) {}
}

function sesToggle() {
    sesAktif = !sesAktif;
    const btn = document.getElementById('ses-butonu');
    if (!btn) return;
    const icon = btn.querySelector('i');
    if (sesAktif) {
        btn.classList.remove('muted');
        if (icon) icon.className = 'fas fa-volume-up';
        if (arkaPlanMuzik) {
            arkaPlanMuzik.play().catch(() => {});
        }
    } else {
        btn.classList.add('muted');
        if (icon) icon.className = 'fas fa-volume-mute';
        if (arkaPlanMuzik) {
            arkaPlanMuzik.pause();
        }
    }
}

function arkaPlanMuzikBaslat() {
    if (!sesAktif) return;
    try {
        arkaPlanMuzik = new Audio('/static/sounds/background.mp3');
        arkaPlanMuzik.loop = true;
        arkaPlanMuzik.volume = 0.15;
        arkaPlanMuzik.play().catch(() => {});
    } catch (e) {}
}

// ---------- FORMAT PARA ----------
function formatPara(sayi) {
    if (sayi >= 1e9) return (sayi / 1e9).toFixed(1) + 'B';
    if (sayi >= 1e6) return (sayi / 1e6).toFixed(1) + 'M';
    if (sayi >= 1e3) return (sayi / 1e3).toFixed(1) + 'K';
    return Math.floor(sayi).toString();
}

// ---------- CARPAN HESAPLA ----------
window.carpanHesapla = () => {
    let carpan = (1.0 + (level * 0.03)) * (1.0 + prestij * 0.15);
    if (personeller["kurgucu"] && personeller["kurgucu"].alinma === 1) carpan *= 1.3;
    return carpan;
};

window.hesaplaFiyat = (esya) => {
    let fiyat = esya.fiyat;
    if (personeller["vergi_uzmani"] && personeller["vergi_uzmani"].alinma === 1) fiyat = Math.floor(fiyat * 0.85);
    return fiyat;
};

// ---------- KAYDET / YÜKLE ----------
window.oyunuKaydet = () => {
    fetch('/kaydet', { method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ bakiye, taraftar, tiklamaGucu, saniyeGeliri, marketEsyalari, level, xp, mesajlar, alinanOduller, prestij, personeller, toplamTiklama })
    });
};

window.oyunuYukle = async () => {
    try {
        const res = await fetch('/yukle');
        const data = await res.json();
        if (data.durum !== "yok") {
            bakiye = data.bakiye;
            taraftar = data.taraftar;
            tiklamaGucu = data.tiklamaGucu;
            saniyeGeliri = data.saniyeGeliri;
            marketEsyalari = data.marketEsyalari || {};
            personeller = data.personeller || {};
            level = data.level;
            xp = data.xp;
            xpGereken = level * 100;
            mesajlar = data.mesajlar || [];
            alinanOduller = data.alinanOduller || [];
            prestij = data.prestij || 0;
            toplamTiklama = data.toplamTiklama || 0;
            gunlukOdulAlinmis = data.gunluk_odul_alinmis || false;
            
            window.ekraniGuncelle();
            window.istatistikleriGuncelle();
            window.etkinlikleriGoster();
            window.liderligiGoster();
            window.başarımlariGoster();
            window.gunlukGorevleriGoster();
            window.rakipleriGoster();
            window.dekorasyonlariGoster();
            window.prestijOzelEsyalariGoster();
            window.gunlukOdulKontrol();
            if (mesajlar.length > 0) {
                window.teklifGoster(mesajlar[0]);
            }
        }
    } catch (e) {
        console.error('Yükleme hatası:', e);
    }
};

// ---------- PASİF GELİR ----------
window.pasifGelirDongusu = () => {
    if (pasifInterval) clearInterval(pasifInterval);
    pasifInterval = setInterval(() => {
        if (saniyeGeliri > 0) {
            let kazanc = Math.floor(saniyeGeliri * window.carpanHesapla());
            bakiye += kazanc;
            if (personeller["sosyal_medyaci"] && personeller["sosyal_medyaci"].alinma === 1) {
                taraftar += 1;
            }
            window.ekraniGuncelle();
            window.oyunuKaydet();
        }
    }, 1000);
};

// ---------- TEKLİF SİSTEMİ ----------
window.teklifKontrol = () => {
    setInterval(async () => {
        try {
            const res = await fetch('/teklif_al', { method: 'POST' });
            const data = await res.json();
            if (data.durum === "basarili") {
                await window.oyunuYukle();
                if (mesajlar.length > 0) {
                    window.teklifGoster(mesajlar[0]);
                    sesOynat('offer.mp3');
                }
            }
        } catch (e) {}
    }, 60000);
};

window.teklifGoster = (teklif) => {
    if (!teklif) return;
    const modal = document.getElementById('teklif-modali');
    const baslik = document.getElementById('teklif-baslik');
    const metin = document.getElementById('teklif-metin');
    const kabulBtn = document.getElementById('teklif-kabul');
    const redBtn = document.getElementById('teklif-red');
    if (!modal || !baslik || !metin || !kabulBtn || !redBtn) return;
    baslik.innerText = teklif.baslik;
    metin.innerText = teklif.metin;
    kabulBtn.dataset.id = teklif.id;
    redBtn.dataset.id = teklif.id;
    modal.style.display = 'flex';
};

window.teklifIslem = async (id, aksiyon) => {
    try {
        const res = await fetch('/teklif_islem', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: parseInt(id), aksiyon: aksiyon })
        });
        const data = await res.json();
        if (data.durum === "basarili") {
            await window.oyunuYukle();
            document.getElementById('teklif-modali').style.display = 'none';
            if (mesajlar.length > 0) {
                window.teklifGoster(mesajlar[0]);
            }
        } else {
            alert(data.mesaj || "İşlem başarısız!");
            mesajlar = mesajlar.filter(m => m.id !== parseInt(id));
            document.getElementById('teklif-modali').style.display = 'none';
            window.oyunuKaydet();
            if (mesajlar.length > 0) {
                window.teklifGoster(mesajlar[0]);
            }
        }
    } catch (error) {
        console.error("Teklif işlem hatası:", error);
        mesajlar = mesajlar.filter(m => m.id !== parseInt(id));
        document.getElementById('teklif-modali').style.display = 'none';
        window.oyunuKaydet();
        if (mesajlar.length > 0) {
            window.teklifGoster(mesajlar[0]);
        }
    }
};

// ---------- YAYIN TIKLAMA ----------
window.yayinaTikla = (event) => {
    let kazanc = Math.floor(tiklamaGucu * window.carpanHesapla());
    bakiye += kazanc;
    taraftar += 1;
    toplamTiklama += 1;
    xp += 1;
    if (xp >= xpGereken) {
        level++;
        xp = 0;
        xpGereken = level * 100;
        window.seviyeAtladı();
    }
    window.ekraniGuncelle();
    window.oyunuKaydet();
    window.tiklamaEfektiOlustur(event);
    window.başarımlariKontrolEt();
    sesOynat('click.mp3');
};

window.tiklamaEfektiOlustur = (event) => {
    const el = document.createElement('div');
    el.className = 'tiklama-efekti';
    el.innerText = '+' + Math.floor(tiklamaGucu * window.carpanHesapla());
    const x = event.clientX || event.pageX || 0;
    const y = event.clientY || event.pageY || 0;
    el.style.left = (x - 20) + 'px';
    el.style.top = (y - 20) + 'px';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1000);
};

window.seviyeAtladı = () => {
    const oduller = [
        { tip: 'bakiye', miktar: Math.floor(level * 30) },
        { tip: 'taraftar', miktar: Math.floor(level * 2) },
        { tip: 'tiklamaGucu', miktar: 1 }
    ];
    const secilen = oduller[Math.floor(Math.random() * oduller.length)];
    if (secilen.tip === 'bakiye') bakiye += secilen.miktar;
    else if (secilen.tip === 'taraftar') taraftar += secilen.miktar;
    else if (secilen.tip === 'tiklamaGucu') tiklamaGucu += secilen.miktar;
    alert(`🎉 Seviye atladın! Ödül: ${secilen.miktar} ${secilen.tip === 'bakiye' ? '₺' : secilen.tip === 'taraftar' ? 'taraftar' : 'tıklama gücü'} kazandın!`);
    sesOynat('levelup.mp3');
};

// ---------- ESYA AL ----------
window.esyaAl = (id) => {
    const esya = marketEsyalari[id];
    if(!esya) return;
    let fiyat = window.hesaplaFiyat(esya);
    if(taraftar < esya.gerekenTaraftar) { alert("Yeterli taraftarın yok!"); return; }
    if(bakiye >= fiyat) {
        bakiye -= fiyat;
        if(esya.tur === 'tiklama') tiklamaGucu += esya.guc;
        else saniyeGeliri += esya.guc;
        esya.fiyat = Math.floor(esya.fiyat * esya.fiyatArtisi);
        window.ekraniGuncelle(); 
        window.oyunuKaydet();
    } else { alert("Yetersiz bakiye!"); }
};

// ---------- PERSONEL AL ----------
window.personelAl = (id) => {
    let p = personeller[id];
    if(!p) { console.error("Personel bulunamadı:", id); return; }
    if (p.alinma === 1) { alert("Bu personel zaten alındı!"); return; }
    if(taraftar < p.gerekenTaraftar) { alert("Yeterli taraftarın yok!"); return; }
    if(bakiye >= p.fiyat) { 
        bakiye -= p.fiyat; 
        p.alinma = 1; 
        window.ekraniGuncelle(); 
        window.oyunuKaydet();
        const btn = document.getElementById('btn-per-' + id);
        if (btn) { btn.disabled = true; btn.innerText = '✅ Alındı'; }
        const kilitSpan = document.getElementById(id === 'sosyal_medyaci' ? 'sm-kilit' : id === 'vergi_uzmani' ? 'fu-kilit' : 'pk-kilit');
        if (kilitSpan) kilitSpan.style.display = 'none';
    }
    else { alert("Bütçen yetersiz!"); }
};

// ---------- PRESTİJ ----------
window.prestijIslemiBaslat = async () => {
    const gerekliLevel = (prestij + 1) * 10;
    if (level < gerekliLevel) {
        alert(`Prestij yapmak için en az Seviye ${gerekliLevel} olmalısın! (Şu an: ${level})`);
        return;
    }
    if(confirm("Tüm gelişimin sıfırlanacak, emin misin?")) {
        const res = await fetch('/prestij_yap', { method: 'POST' });
        const data = await res.json();
        if (data.durum === "basarili") {
            window.location.reload();
        } else {
            alert("Prestij işlemi sırasında hata oluştu!");
        }
    }
};

// ---------- GÜNLÜK ÖDÜL ----------
window.gunlukOdulKontrol = async () => {
    try {
        const res = await fetch('/gunluk_odul');
        const data = await res.json();
        const btn = document.getElementById('gunluk-odul-btn');
        if (!btn) return;
        if (data.durum === 'alabilir') {
            btn.disabled = false;
            btn.innerText = '🎁 Günlük Ödülü Al!';
            btn.style.background = '#f1c40f';
        } else {
            btn.disabled = true;
            btn.innerText = '✅ Bugün aldın';
            btn.style.background = '#4ade80';
        }
    } catch (e) {
        console.error('Günlük ödül kontrol hatası:', e);
    }
};

window.gunlukOdulAl = async () => {
    try {
        const res = await fetch('/gunluk_odul_al', { method: 'POST' });
        const data = await res.json();
        if (data.durum === 'basarili') {
            alert(`🎁 Günlük ödülü kazandın! ${data.odul_bakiye}₺ ve ${data.odul_taraftar} taraftar.`);
            await window.oyunuYukle();
            window.gunlukOdulKontrol();
        } else {
            alert(data.mesaj || 'Ödül alınamadı!');
        }
    } catch (e) {
        console.error('Ödül alma hatası:', e);
        alert('Bir hata oluştu, lütfen tekrar deneyin.');
    }
};

// ---------- İSTATİSTİKLER ----------
window.istatistikleriGuncelle = async () => {
    try {
        const res = await fetch('/istatistikler');
        const data = await res.json();
        const liste = document.getElementById('istatistik-listesi');
        if (!liste) return;
        if (data.durum !== 'yok') {
            const saat = Math.floor(data.toplam_yayin_suresi / 3600);
            const dakika = Math.floor((data.toplam_yayin_suresi % 3600) / 60);
            liste.innerHTML = `
                <div class="istatistik-karti">
                    <div><span>⏱️ Yayın Süresi</span><span>${saat}s ${dakika}d</span></div>
                    <div><span>💰 Toplam Kazanılan</span><span>${formatPara(data.toplam_kazanilan_para)} ₺</span></div>
                    <div><span>👥 Toplam Kazanılan Taraftar</span><span>${formatPara(data.toplam_kazanilan_taraftar)}</span></div>
                    <div><span>🖱️ Toplam Tıklama</span><span>${formatPara(data.toplam_tiklama)}</span></div>
                    <div><span>📈 En Yüksek Gelir</span><span>${formatPara(data.en_yuksek_gelir)} ₺/sn</span></div>
                </div>
            `;
        } else {
            liste.innerHTML = '<p>İstatistik henüz toplanmadı.</p>';
        }
    } catch (e) {
        console.error('İstatistik hatası:', e);
    }
};

// ---------- ETKİNLİKLER ----------
window.etkinlikleriGoster = async () => {
    try {
        const res = await fetch('/etkinlikler');
        const etkinlikler = await res.json();
        const liste = document.getElementById('etkinlik-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        if (etkinlikler.length === 0) {
            liste.innerHTML = '<p>Şu anda aktif etkinlik yok.</p>';
            return;
        }
        const progRes = await fetch('/etkinlik_progress');
        const progress = await progRes.json();
        const progMap = {};
        progress.forEach(p => { progMap[p.etkinlik_id] = p; });

        for (let e of etkinlikler) {
            const div = document.createElement('div');
            div.className = 'etkinlik-karti';
            const p = progMap[e.id] || { progress: 0, tamamlandi: false };
            div.innerHTML = `
                <div><span>${e.name}</span><span>${p.tamamlandi ? '✅ Tamamlandı' : '⏳ Devam'}</span></div>
                <small>${e.description}</small>
                <button onclick="etkinlikTamamla(${e.id})" ${p.tamamlandi ? 'disabled' : ''}>
                    ${p.tamamlandi ? '✅ Tamamlandı' : `Ödülü Al (${e.reward_amount} ${e.reward_type})`}
                </button>
            `;
            liste.appendChild(div);
        }
    } catch (e) {
        console.error('Etkinlik hatası:', e);
    }
};

window.etkinlikTamamla = async (etkinlik_id) => {
    try {
        const res = await fetch('/etkinlik_tamamla', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ etkinlik_id })
        });
        const data = await res.json();
        if (data.durum === 'basarili') {
            alert(`🎉 Etkinlik tamamlandı! ${data.reward_amount} ${data.reward_type} kazandın!`);
            await window.oyunuYukle();
            window.etkinlikleriGoster();
        } else {
            alert(data.mesaj || 'Etkinlik tamamlanamadı!');
        }
    } catch (e) {
        console.error('Etkinlik tamamlama hatası:', e);
    }
};

// ---------- LİDERLİK ----------
window.liderligiGoster = async () => {
    try {
        const res = await fetch('/liderlik');
        const liderler = await res.json();
        const liste = document.getElementById('liderlik-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        if (liderler.length === 0) {
            liste.innerHTML = '<p>Henüz liderlik verisi yok.</p>';
            return;
        }
        for (let l of liderler) {
            const div = document.createElement('div');
            div.className = 'liderlik-karti';
            div.innerHTML = `
                <div><span>#${l.sira} ${l.kullanici}</span><span>🎖️ Prestij: ${l.prestij}</span></div>
                <div><span>⭐ Seviye: ${l.level}</span><span>💰 ${formatPara(l.toplam_gelir)} ₺</span></div>
                <div><span>👥 ${formatPara(l.toplam_taraftar)} Taraftar</span></div>
            `;
            liste.appendChild(div);
        }
    } catch (e) {
        console.error('Liderlik hatası:', e);
    }
};

// ---------- BAŞARIMLAR ----------
window.başarımlariKontrolEt = async () => {
    try {
        const res = await fetch('/achievements');
        const basarimlar = await res.json();
        const yeni = basarimlar.filter(b => b.unlocked && !window.alinanOduller.includes(b.id));
        if (yeni.length > 0) {
            for (let b of yeni) {
                alert(`🏆 Başarım Açıldı: ${b.name}\n${b.description}\nÖdül: ${b.reward_amount} ${b.reward_type}`);
                if (b.reward_type === 'bakiye') bakiye += b.reward_amount;
                else if (b.reward_type === 'taraftar') taraftar += b.reward_amount;
                else if (b.reward_type === 'tiklamaGucu') tiklamaGucu += b.reward_amount;
                window.alinanOduller.push(b.id);
                window.ekraniGuncelle();
                window.oyunuKaydet();
            }
        }
    } catch (e) {
        console.error('Başarımlar kontrol hatası:', e);
    }
};

window.başarımlariGoster = async () => {
    try {
        const res = await fetch('/achievements');
        const basarimlar = await res.json();
        const liste = document.getElementById('basari-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        basarimlar.forEach(b => {
            const div = document.createElement('div');
            div.className = 'basari-karti' + (b.unlocked ? ' unlocked' : ' locked');
            div.innerHTML = `
                <div><span>${b.icon} ${b.name}</span><span>${b.unlocked ? '✅' : '🔒'}</span></div>
                <small>${b.description}</small>
            `;
            liste.appendChild(div);
        });
    } catch (e) {
        console.error('Başarımlar gösterme hatası:', e);
    }
};

// ---------- GÜNLÜK GÖREVLER ----------
window.gunlukGorevleriGoster = async () => {
    try {
        const res = await fetch('/daily_quests');
        const gorevler = await res.json();
        const liste = document.getElementById('gunluk-gorev-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        gorevler.forEach(g => {
            const div = document.createElement('div');
            div.className = 'gorev-karti' + (g.completed ? ' tamamlandi' : '');
            div.innerHTML = `
                <div><span>${g.name}</span><span>${g.progress}/${g.condition_value}</span></div>
                <button onclick="gunlukGorevTamamla(${g.id})" ${g.completed ? 'disabled' : ''}>
                    ${g.completed ? '✅ Tamamlandı' : 'Ödülü Al'}
                </button>
                <small>${g.description} (${g.reward_amount} ${g.reward_type})</small>
            `;
            liste.appendChild(div);
        });
    } catch (e) {
        console.error('Görevler gösterme hatası:', e);
    }
};

window.gunlukGorevTamamla = async (quest_id) => {
    try {
        const res = await fetch('/claim_daily_quest', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ quest_id })
        });
        const data = await res.json();
        if (data.durum === 'basarili') {
            await window.oyunuYukle();
            window.gunlukGorevleriGoster();
            window.ekraniGuncelle();
        } else {
            alert(data.mesaj || 'Görev tamamlanamadı!');
        }
    } catch (e) {
        console.error('Görev tamamlama hatası:', e);
    }
};

// ---------- RAKİPLER ----------
window.rakipleriGoster = async () => {
    try {
        const res = await fetch('/ai_opponents');
        const rakipler = await res.json();
        const liste = document.getElementById('rakip-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        rakipler.forEach(r => {
            const div = document.createElement('div');
            div.className = 'rakip-karti';
            div.innerHTML = `
                <div><span>${r.icon} ${r.name}</span><span>Gelir: ${formatPara(r.income)} ₺/sn | Taraftar: ${formatPara(r.followers)}</span></div>
                <button onclick="rakipMeydanOku(${r.id})">⚔️ Meydan Oku</button>
            `;
            liste.appendChild(div);
        });
    } catch (e) {
        console.error('Rakipler gösterme hatası:', e);
    }
};

window.rakipMeydanOku = async (ai_id) => {
    try {
        const res = await fetch('/challenge_ai', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ai_id })
        });
        const data = await res.json();
        if (data.durum === 'kazandi') {
            alert(`🎉 Rakibi yendin! ${data.odul} ₺ kazandın!`);
            await window.oyunuYukle();
            window.ekraniGuncelle();
        } else {
            alert('😞 Rakibe yenildin! Daha güçlenip tekrar dene.');
        }
    } catch (e) {
        console.error('Rakip meydan okuma hatası:', e);
    }
};

// ---------- DEKORASYONLAR ----------
window.dekorasyonlariGoster = async () => {
    try {
        const res = await fetch('/studio_decorations');
        const dekorlar = await res.json();
        const liste = document.getElementById('dekorasyon-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        dekorlar.forEach(d => {
            const div = document.createElement('div');
            div.className = 'dekorasyon-karti' + (d.owned ? ' sahip' : '');
            div.innerHTML = `
                <div><span>${d.icon} ${d.name}</span><span>${d.owned ? (d.equipped ? '✅ Kullanımda' : 'Sahip') : formatPara(d.price) + ' ₺'}</span></div>
                <button onclick="${d.owned ? `dekorasyonKullan(${d.id})` : `dekorasyonSatınAl(${d.id})`}">
                    ${d.owned ? (d.equipped ? 'Kullanımda' : 'Kullan') : 'Satın Al'}
                </button>
                <small>${d.description}</small>
            `;
            liste.appendChild(div);
        });
    } catch (e) {
        console.error('Dekorasyon gösterme hatası:', e);
    }
};

window.dekorasyonSatınAl = async (id) => {
    try {
        const res = await fetch('/buy_decoration', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ decoration_id: id })
        });
        const data = await res.json();
        if (data.durum === 'basarili') {
            await window.oyunuYukle();
            window.dekorasyonlariGoster();
            window.ekraniGuncelle();
        } else {
            alert(data.mesaj || 'Satın alma başarısız!');
        }
    } catch (e) {
        console.error('Dekorasyon satın alma hatası:', e);
    }
};

window.dekorasyonKullan = async (id) => {
    try {
        const res = await fetch('/equip_decoration', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ decoration_id: id })
        });
        const data = await res.json();
        if (data.durum === 'basarili') {
            await window.oyunuYukle();
            window.dekorasyonlariGoster();
        } else {
            alert('Kullanım hatası!');
        }
    } catch (e) {
        console.error('Dekorasyon kullanma hatası:', e);
    }
};

// ---------- LOOT KUTUSU ----------
window.lootKutusuAc = async (box_id) => {
    try {
        const res = await fetch('/open_lootbox', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ box_id })
        });
        const data = await res.json();
        if (data.durum === 'basarili') {
            alert(`🎁 Kutu açıldı! ${data.reward_amount} ${data.reward_type} kazandın!`);
            await window.oyunuYukle();
            window.ekraniGuncelle();
        } else {
            alert('Kutu açılamadı!');
        }
    } catch (e) {
        console.error('Loot kutusu hatası:', e);
    }
};

// ---------- PRESTİJ ÖZEL EŞYALAR ----------
window.prestijOzelEsyalariGoster = async () => {
    try {
        const res = await fetch('/prestige_special_items');
        const items = await res.json();
        const liste = document.getElementById('ozel-esya-listesi');
        if (!liste) return;
        liste.innerHTML = '';
        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'ozel-esya-karti';
            div.innerHTML = `
                <div><span>${item.icon} ${item.name}</span><span>Prestij ${item.required_prestige}</span></div>
                <small>${item.description} (+${item.bonus_value} ${item.bonus_type})</small>
            `;
            liste.appendChild(div);
        });
    } catch (e) {
        console.error('Prestij özel eşyalar hatası:', e);
    }
};

// ---------- PRESTİJ MODAL ----------
window.prestijModalAc = () => {
    document.getElementById("prestij-modali").style.display = "flex";
    const gerekliLevel = (prestij + 1) * 10;
    document.getElementById("mevcut-carpan-metni").innerText = 'x' + (1 + prestij * 0.15).toFixed(2);
    document.getElementById("sonraki-carpan-metni").innerText = 'x' + (1 + (prestij+1) * 0.15).toFixed(2);
    document.getElementById("prestij-sart-metni").innerText = `Gerekli Seviye: ${gerekliLevel} (Şu an: ${level})`;
    const btn = document.getElementById("btn-prestij-yap");
    if (level >= gerekliLevel) {
        btn.disabled = false;
        btn.style.opacity = "1";
        btn.style.cursor = "pointer";
    } else {
        btn.disabled = true;
        btn.style.opacity = "0.5";
        btn.style.cursor = "not-allowed";
    }
};

// ---------- EKRAN GÜNCELLEME ----------
window.ekraniGuncelle = () => {
    if(document.getElementById("bakiye-gosterge")) document.getElementById("bakiye-gosterge").innerText = formatPara(bakiye) + " ₺";
    if(document.getElementById("taraftar-gosterge")) document.getElementById("taraftar-gosterge").innerText = formatPara(taraftar);
    if(document.getElementById("level-gosterge")) document.getElementById("level-gosterge").innerText = level;
    if(document.getElementById("saniye-geliri-metni")) document.getElementById("saniye-geliri-metni").innerText = formatPara(Math.floor(saniyeGeliri * window.carpanHesapla())) + " ₺/sn";
    if(document.getElementById("prestij-gosterge")) document.getElementById("prestij-gosterge").innerText = prestij;
    
    const xpBar = document.getElementById("xp-bar-ic");
    const xpYazi = document.getElementById("xp-yazi");
    if (xpBar) {
        const yuzde = (xp / xpGereken) * 100;
        xpBar.style.width = Math.min(yuzde, 100) + '%';
    }
    if (xpYazi) {
        xpYazi.innerText = `${Math.floor(xp)} / ${xpGereken} XP`;
    }
    
    for (let id in marketEsyalari) {
        const esya = marketEsyalari[id];
        const fiyatSpan = document.getElementById(id + '-fiyat');
        if (fiyatSpan) {
            const fiyat = window.hesaplaFiyat(esya);
            fiyatSpan.innerText = formatPara(fiyat);
        }
        const kilitMetni = document.getElementById(id + '-kilit');
        if (kilitMetni) {
            kilitMetni.style.display = (taraftar >= esya.gerekenTaraftar) ? 'none' : 'block';
        }
        const btn = document.getElementById('btn-' + id);
        if (btn) {
            if (taraftar >= esya.gerekenTaraftar) btn.classList.remove('kilitli');
            else btn.classList.add('kilitli');
        }
    }
    
    for (let id in personeller) {
        const p = personeller[id];
        const btn = document.getElementById('btn-per-' + id);
        if (btn) {
            if (p.alinma === 1) {
                btn.disabled = true;
                btn.innerText = '✅ Alındı';
            } else {
                btn.disabled = false;
                btn.innerText = formatPara(p.fiyat) + ' ₺';
                const kilitSpan = document.getElementById(id === 'sosyal_medyaci' ? 'sm-kilit' : id === 'vergi_uzmani' ? 'fu-kilit' : 'pk-kilit');
                if (kilitSpan) {
                    kilitSpan.style.display = (taraftar >= p.gerekenTaraftar) ? 'none' : 'inline';
                }
            }
        }
    }
};

// ---------- DOM YÜKLENDİ ----------
document.addEventListener('DOMContentLoaded', () => {
    const btns = document.querySelectorAll('.sekme-btn');
    const paneller = document.querySelectorAll('.sekme-panel');

    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const hedef = btn.dataset.sekme;
            paneller.forEach(p => p.classList.remove('aktif'));
            const hedefPanel = document.getElementById('sekme-' + hedef);
            if (hedefPanel) hedefPanel.classList.add('aktif');
        });
    });

    const kabulBtn = document.getElementById('teklif-kabul');
    const redBtn = document.getElementById('teklif-red');
    if (kabulBtn) {
        kabulBtn.addEventListener('click', function() {
            const id = this.dataset.id;
            window.teklifIslem(id, 'kabul');
        });
    }
    if (redBtn) {
        redBtn.addEventListener('click', function() {
            const id = this.dataset.id;
            window.teklifIslem(id, 'red');
        });
    }
});

// ---------- SAYFA YÜKLENDİ ----------
window.onload = async () => { 
    await window.oyunuYukle();
    window.pasifGelirDongusu();
    window.teklifKontrol();
    // Arka plan müziğini başlat
    setTimeout(() => {
        arkaPlanMuzikBaslat();
    }, 1000);
};