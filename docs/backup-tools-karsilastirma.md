# Linux ext4 Yedekleme Araclari Kapsamli Karsilastirma

**Tarih:** 2026-03-10
**Mevcut sistem:** rsync + hardlink tabanli snapshot, GRUB entegrasyonu ile boot-time restore
**Dosya sistemi:** ext4 (NVMe, 481GB)

---

## 1. Mevcut Sistem: rsync + Hardlink

### Nasil Calisiyor
Her snapshot diskte tam bir dizin agaci olarak gorunur. Degismemis dosyalar onceki snapshot'a hardlink ile baglanir, yalnizca degisen dosyalar yeni disk alani tuketir. Dosya seviyesinde dedup yapar (ayni dosya = ayni inode).

### Avantajlar
- **Sadelik:** Restore islemi basit bir rsync veya cp. Ozel bir arac gerektirmez.
- **GRUB entegrasyonu:** Snapshot dizinleri dogrudan dosya sistemi uzerinde gorunur. GRUB ext4 driver'i ile snapshot icindeki dosyalara erisebilir. Mevcut restore script'in (PID 1 olarak calisan) rsync ile geri yukleme yapisi buna mukemmel uyuyor.
- **Dogrulama kolayligi:** `ls`, `diff`, `cat` ile snapshot icerigini aninda kontrol edebilirsin. Ozel bir extract komutu gerekmez.
- **Guvenilirlik:** Veri formati duz dosya/dizin. Bozulma riski minimum — bir dosya bozulsa bile digerleri etkilenmez.
- **Hiz:** Incremental backup rsync ile cok hizli. Restore da rsync hizinda.

### Dezavantajlar
- **Alan verimliligi sinirli:** Dosya icinde kucuk bir degisiklik olsa bile (ornegin 2GB'lik bir log dosyasina 1 satir eklenmesi) dosyanin tamami yeniden kopyalanir. Chunk-based dedup bu durumda yalnizca degisen chunk'i kaydeder.
- **Inode tuketimi:** Her snapshot'ta her dosya bir inode kullanir (ayni inode olsa bile hardlink sayisi artar). Cok fazla snapshot tutulursa inode limiti sorun olabilir (ext4'te genelde sorun degil ama dikkat edilmeli).
- **Sikistirma yok:** Veriler oldugu gibi saklanir. Sikistirmali araclar %30-50 daha az alan kullanabilir.
- **Sifreleme yok:** Harici diske yedekleniyorsa veri acik durur (LUKS ile disk seviyesinde sifrelenebilir ama arac seviyesinde degil).
- **Dosyalar arasi dedup yok:** Iki farkli dosya ayni icerige sahip olsa bile (farkli isim/konum) ayri ayri saklanir.

### Gercek Dunya Alan Kullanimi
Tipik bir masaustu/gelistirme sisteminde gunluk snapshot'lar icin degisim orani %1-5 civarindadir. 10 snapshot tutuyorsan yaklasik 1.5-2x disk alani kullanirsin (ornegin 100GB sistem icin ~150-200GB).

---

## 2. Borg Backup

### Genel Bakis
Content-defined chunking (CDC) ile chunk seviyesinde dedup. Python/Cython ile yazilmis. En olgun dedup yedekleme araci.

### Avantajlar
- **Mukemmel dedup:** Dosya ici degisikliklerde bile yalnizca degisen chunk'lar kaydedilir. Tipik olarak %60-80 dedup orani.
- **Guclu sikistirma:** lz4, zstd, zlib destegi. Sikistirma + dedup birlikte %70-90 alan tasarrufu saglayabilir.
- **Sifreleme:** AES-256 ile client-side sifreleme.
- **Olgunluk:** 2010'dan beri gelistiriliyor, genis topluluk, iyi dokumantasyon.
- **SSH tabanli uzak yedekleme:** Ek altyapi gerektirmez.

### Dezavantajlar
- **Repo formati opak:** Snapshot icerigini gormek icin `borg extract` veya `borg mount` (FUSE) kullanilmali. GRUB dogrudan okuyamaz.
- **GRUB entegrasyonu MUMKUN DEGIL:** Borg repo'su icindeki dosyalara GRUB erisemez. Restore icin once canli bir Linux ortami (live USB veya initramfs) gerekir, oradan borg extract yapilir.
- **Repo bozulma riskleri:** GitHub'da bilinen sorunlar var — `borg check --repair` bazen sonsuz donguye giriyor (issue #5995, #4243). Bozulma ayda 1-2 kez bile raporlanmis (issue #4829). Repair islemi veri kaybina yol acabilir.
- **Borg 2.0 hala beta:** 2022'den beri beta surecinde, Aralik 2025'te b20 cikti. Stabil 2.0 henuz yayinlanmadi. 1.x -> 2.x gecisi uyumsuz (repo migrasyon gerekir).
- **Performans kaygilari:** Bazi kullanicilar buyuk veri setlerinde yedeklemenin 6+ saat surdugunu raporlamis.
- **Tek gelistirici riski:** Ana gelistirici sayisi sinirli, topluluk katkilari var ama core gelistirme dar.
- **Restore hizi en yavas:** Benchmark'larda Restic ve Kopia'dan yavas (39MB arsiv icin 18-19sn vs Restic 8sn).

### ext4 ile Bilinen Sorunlar
ext4 uzerinde calismasi sorunsuz. Borg dokumantasyonu ext4'u "kanitlanmis dosya sistemi" olarak oneriyor.

### Bakim Gereksinimleri
- `borg check` duzenli calistirilmali (repo butunluk kontrolu)
- `borg prune` ile eski arsivlerin temizligi
- `borg compact` ile bos chunk'larin geri kazanimi

---

## 3. Restic

### Genel Bakis
Go ile yazilmis, tek binary. Content-defined chunking. Cloud storage (S3, B2, Azure, GCS) destegi guclu.

### Avantajlar
- **Tek binary:** Bagimliligi yok, kurulumu kolay.
- **Cloud destegi:** S3, Backblaze B2, Azure, GCS, SFTP vs. native destekli.
- **Restore hizi en iyi:** Benchmark'larda birinci sirada.
- **Iyi dedup:** %60-80 dedup orani.
- **Aktif gelistirme:** Duzgun release dongusu, genis topluluk.

### Dezavantajlar
- **Prune islemi cok yavas:** Bu en buyuk sikayettir. 50GB'lik repo icin prune 16-24 saat surebilir. Buyuk repo'larda haftalar surebilir. Prune sirasinda repo kilitlenir — yeni yedekleme alinamaz.
- **GRUB entegrasyonu MUMKUN DEGIL:** Borg ile ayni sorun — opak repo formati.
- **Sikistirma gecmisi:** Sikistirma destegi gecte eklendi (v0.14+), Borg kadar esnek degil.
- **ext4 uzerinde repo performansi:** Restic 256+ dizin olusturur, bu ext4'te performans sorunlarina yol acabilir (ozellikle buyuk repo'larda).
- **Bare metal restore karmasik:** Manuel olarak disk partition, format, mount, restic restore, GRUB reinstall adimlari gerekir.
- **Sifreleme zorunlu:** Sifrelemeyi kapatma secenegi yok (yerel yedekleme icin gereksiz CPU yuku).

### ext4 ile Bilinen Sorunlar
ext4 + SMR disk kombinasyonunda ciddi performans sorunlari raporlanmis. NVMe/SSD uzerinde genelde sorunsuz.

### Bakim Gereksinimleri
- `restic forget --prune` duzenli calistirilmali (ve cok uzun surer!)
- `restic check` ile butunluk kontrolu

---

## 4. Kopia

### Genel Bakis
Go ile yazilmis, en yeni arac. GUI ve CLI destegi. Content-defined chunking + gelismis sikistirma.

### Avantajlar
- **En iyi sikistirma:** zstd destegi, %65-82 dedup orani.
- **GUI mevcut:** Web tabanli arayuz, diger araclarda yok.
- **Paralel islem:** Ozellikle cloud storage'a paralel chunk upload ile en hizli.
- **Backup suresi trend olarak iyilesiyor:** Diger araclarin aksine backup suresi zamanla artmiyor.
- **Bakim otomatik:** Snapshot/repo dogrulama otomatik yapiliyor.
- **Cloud-native:** Modern cloud storage icin optimize.

### Dezavantajlar
- **En genc proje:** Olgunluk acisindan Borg ve Restic'in gerisinde.
- **GRUB entegrasyonu MUMKUN DEGIL:** Ayni opak repo formati sorunu.
- **Bilinen hatalar (2025-2026):**
  - Buyuk veri setlerinde full maintenance takilabiliyor (Synology NAS'ta raporlandi)
  - Dosya boyutu tahmini yanlis (11GB tahmin, gercekte 1-2GB)
  - Repository olusturulduktan sonra sifreleme algoritmasi degistirilemiyor
- **Topluluk daha kucuk:** Borg ve Restic'e kiyasla daha az kullanici, daha az battle-tested.
- **Object lock/retention politikasi sinirli:** Farkli snapshot'lar icin farkli retention suresi ayarlanamaz.

### ext4 ile Bilinen Sorunlar
Ozel bir ext4 sorunu raporlanmamis. Genel olarak sorunsuz calisiyor.

### Bakim Gereksinimleri
- Otomatik bakim calisir ama buyuk repo'larda sorun cikarabilir
- Manuel `kopia maintenance run --full` gerekebilir

---

## 5. Btrfs Snapshot'larina Gecis

### Nasil Calisiyor
Btrfs, dosya sistemi seviyesinde Copy-on-Write (CoW) snapshot destegi sunar. Snapshot alindiginda yalnizca metadata kopyalanir, veri bloklari paylasilir.

### Avantajlar
- **Anlik snapshot:** Milisaniyeler icinde alinir, boyut bagimsiz.
- **Alan verimli:** Block seviyesinde CoW — yalnizca degisen bloklar yeni alan tuketir.
- **Checksum destegi:** ext4'te olmayan veri butunlugu kontrolu (silent corruption tespiti).
- **Scrub:** Disk uzerinde checksum dogrulamasi, bozuk veriyi tespit eder.
- **send/receive:** Snapshot'lari baska bir diske incremental olarak gonderebilirsin.

### Dezavantajlar ve Riskler
- **Dosya sistemi degisikligi gerekli:** ext4 -> Btrfs gecisi temiz kurulum veya `btrfs-convert` gerektirir. `btrfs-convert` riskli ve buyuk disklerde sorunlu olabilir.
- **GRUB destegi var AMA:** Btrfs snapshot'lari GRUB ile calisiyor (grub-btrfs projesi), ancak mevcut snapshot-manager'in tamami yeniden yazilmasi gerekir.
- **Performans overhead'i:** CoW mekanizmasi buyuk ardisik yazmalarda ext4'e gore yavas (%10-20 performans kaybi).
- **RAID 5/6 hala stabil degil:** Ocak 2026 itibariyle Btrfs RAID 5/6 uretimde onerilmiyor.
- **Karmasiklik:** Subvolume yonetimi, balance, quota gibi kavramlar ogrenilmeli.
- **Dual-boot riski:** Windows Btrfs okuyamaz (mevcut sistemde dual-boot var).
- **NVMe uzerinde CoW fragmentasyonu:** SSD'lerde buyuk sorun degil ama HDD'lerde ciddi fragmentasyon olabilir.

### Degisime Deger mi?
Eger **yalnizca snapshot/yedekleme** icin dusunuluyorsa, riskleri avantajlarina agir basar. Mevcut ext4 + rsync + hardlink sistemi guvenilir calisiyor ve GRUB entegrasyonu mevcut. Btrfs'e gecis tamamen yeni bir altyapi ve yeni riskler demek.

---

## Karsilastirma Tablosu

| Ozellik | rsync+hardlink | Borg | Restic | Kopia | Btrfs snapshot |
|---------|---------------|------|--------|-------|----------------|
| Dedup seviyesi | Dosya | Chunk | Chunk | Chunk | Block (CoW) |
| Tipik alan tasarrufu (10 snapshot) | %40-60 | %70-90 | %65-85 | %70-88 | %80-95 |
| Sikistirma | Yok | Var (lz4/zstd/zlib) | Var (zstd) | Var (zstd) | Var (zstd/lzo) |
| Sifreleme | Yok (LUKS ile) | AES-256 | AES-256 (zorunlu) | AES-256 | Yok (LUKS ile) |
| GRUB'dan erisilebilirlik | EVET | HAYIR | HAYIR | HAYIR | EVET (grub-btrfs) |
| Restore basitligi | cp/rsync | borg extract | restic restore | kopia restore | cp/rsync (snapshot mount) |
| Bare metal restore | Cok kolay | Karmasik | Karmasik | Karmasik | Kolay (eger btrfs ise) |
| Repo bozulma riski | Cok dusuk | Orta | Dusuk | Dusuk | Dusuk (checksum) |
| Bakim gereksinimi | Yok | check + prune + compact | forget + prune (YAVAS) | Otomatik | balance + scrub |
| ext4 uyumlulugu | Mukemmel | Iyi | Iyi (SMR dikkat) | Iyi | ext4 DEGIL |
| Olgunluk | 25+ yil | 15+ yil | 10+ yil | 5+ yil | 15+ yil |
| Aktif gelistirme (2026) | rsync aktif | Aktif (2.0 beta) | Aktif | Aktif | Aktif (kernel) |

---

## Senaryoya Ozel Degerlendirme

### Senin Sistemin Icin (snapshot-manager + GRUB restore)

Mevcut sisteminin **en kritik ozelligi**: GRUB menusunden secim yaparak, PID 1 olarak calisan bir restore script'inin rsync ile sistemi geri yuklemesi. Bu ozellik **yalnizca dosya sistemi uzerinde dogrudan erisilebilir snapshot'larla** mumkun.

**Borg/Restic/Kopia kullanirsan:**
1. GRUB'dan dogrudan restore **mumkun degil**
2. Once live USB ile boot etmen gerekir
3. Sonra araci kurup repo'yu acman gerekir
4. Extract edip GRUB'u yeniden kurman gerekir
5. Bu, mevcut "3 tusla restore" deneyimini tamamen ortadan kaldirir

**Chunk-based dedup'un sana kazandirabilecegi alan:**
- Mevcut sistemin ~100GB sistem verisi ile 10 snapshot tutuyor diyelim
- rsync+hardlink: ~150-200GB (degisim oranina bagli)
- Chunk-based dedup + sikistirma: ~80-120GB
- Net kazanc: ~50-80GB (NVMe diskte bu buyuk bir fark degil)

### Oneriler

1. **Mevcut sistemi koru.** GRUB entegrasyonu ile boot-time restore ozelligi cok degerli ve chunk-based araclarin hicbiri bunu saglayamaz.

2. **Hibrit yaklasim dusun:** Mevcut snapshot-manager'i birincil restore araci olarak tut. Ek olarak Borg veya Restic ile haftalik/aylik uzak yedekleme al (NAS, bulut vs.). Boylece:
   - Hizli restore: GRUB -> snapshot-manager (mevcut)
   - Felaket kurtarma: Borg/Restic ile uzak yedekten restore (live USB gerekir ama bu zaten felaket senaryosu)

3. **Eger yalnizca bir arac secilecekse:**
   - **Yerel restore onceligi:** rsync+hardlink (mevcut) en iyisi
   - **Uzak yedekleme onceligi:** Borg (en olgun, en iyi dedup)
   - **Cloud yedekleme onceligi:** Restic veya Kopia

4. **Btrfs'e gecme.** Mevcut ext4 sistemi guvenilir calisiyor, dual-boot'un var, ve gecis ciddi risk icerir. Kazanc/risk orani dusuk.

5. **snapshot-manager'a sikistirma ekle:** Eger alan tasarrufu istiyorsan, rsync sonrasi snapshot dizinini `zstd` ile sikistirip tar olarak saklama secenegi eklenebilir (ancak bu GRUB erisilebilirligini ortadan kaldirir, yani yalnizca eski arsivler icin mantikli olur).

---

## Sonuc

Chunk-based dedup araclari (Borg, Restic, Kopia) alan tasarrufu konusunda rsync+hardlink'ten ustun. Ancak senin kullanim senaryonda **GRUB entegrasyonu ve aninda restore** en kritik ozellik. Bu araclarin hicbiri bunu saglayamaz.

**En pragmatik yaklasim:** Mevcut snapshot-manager'i birincil olarak kullanmaya devam et, ihtiyac duyarsan Borg ile ikincil uzak yedekleme ekle. Alan sorunu yasarsan eski snapshot'lari Borg'a arsivleyip yerel olarak sil.

---

*Kaynaklar: Borg/Restic/Kopia resmi dokumantasyonlari, patpro.net benchmark serisi, grigio.org hiz testleri, GitHub issue tracker'lari, topluluk forumlari.*
