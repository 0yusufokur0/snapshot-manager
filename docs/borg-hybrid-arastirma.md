# Borg Hybrid Backend Arastirma Raporu

**Tarih:** 2026-03-11
**Konu:** rsync+hardlink snapshot-manager'a Borg archival backend eklenmesi

---

## 1. Rsync+Borg Hibrit Pattern: Mevcut Uygulamalar

### Bulunan Acik Kaynak Projeler

**a) borg-import (resmi)** — https://github.com/borgbackup/borg-import
- BorgBackup ekibinin resmi araci
- `borg-import rsynchl` komutu ile rsync+hardlink yedeklerini Borg'a aktarir
- Her rsync snapshot icin ayri bir Borg arsivi olusturur
- Timestamp'i dizin adindan cikarir

**b) borgsnap** — https://github.com/scotte/borgsnap
- ZFS snapshot'larindan Borg arsivleri olusturur
- rsync.net entegrasyonu var
- Pattern: snapshot al -> borg create -> eski snapshot'lari sil

**c) Yaygin Kullanim Pattern'i** (blog yazilari):
- rsync ile dosyalari uzak makineye kopyala
- Uzak makinede borg create ile arsivle
- Kaynak: https://jstaf.github.io/posts/backups-with-borg-rsync/
- Kaynak: https://dizzard.net/articles/borg_rsync/article.html

### Bizim Icin En Uygun Pattern

```
[Canli Sistem] --rsync+hardlink--> [Yerel Snapshot]
                                         |
                                         v
                                   [Borg Create]
                                         |
                                         v
                                  [Borg Repository]
```

**Akis:**
1. rsync+hardlink ile hizli snapshot al (mevcut sistem)
2. Borg ile eski snapshot'lari arsivle (yeni ozellik)
3. Arsivlenen snapshot'lari rsync tarafindan sil
4. Gerektiginde borg extract ile geri yukle

---

## 2. Borg Create — Yerel Dizinden Arsivleme

### Evet, Mumkun ve Onerilen Bir Yontem

Borg, herhangi bir yerel dizinden arsiv olusturabilir. Root filesystem olmak zorunda degil.

```bash
# Ornek: Snapshot dizininden arsiv olusturma
borg create /borg-repo::system_2026-03-08_14-30-00 \
    /snapshots/system_2026-03-08_14-30-00/fs/

# Slashdot hack ile path prefix'i kirpma
borg create /borg-repo::system_2026-03-08_14-30-00 \
    /snapshots/system_2026-03-08_14-30-00/fs/./

# Veya cd ile relative path
cd /snapshots/system_2026-03-08_14-30-00/fs/
borg create /borg-repo::system_2026-03-08_14-30-00 .
```

### Dikkat Edilmesi Gerekenler

**Path Sorunu:** Borg `--files-cache` mutlak yol kullanir. Farkli snapshot dizinlerinden
arsiv olustururken (ornegin `/snapshots/system_2026-03-08/fs/` vs
`/snapshots/system_2026-03-09/fs/`), dosya yollari degistigi icin files cache
**calismaz** ve tum dosyalar "yeni eklenmis" olarak gorulur.

**Cozumler:**
```bash
# Cozum 1: Sabit bind mount noktasi kullanmak
mount --bind /snapshots/system_2026-03-08_14-30-00/fs /mnt/snapshot-current
borg create /borg-repo::arsiv_adi /mnt/snapshot-current
umount /mnt/snapshot-current

# Cozum 2: files-cache'i devre disi birakmak
borg create --files-cache disabled /borg-repo::arsiv_adi \
    /snapshots/system_2026-03-08_14-30-00/fs/

# Cozum 3: cd ile sabit relative path
cd /snapshots/system_2026-03-08_14-30-00/fs/
borg create /borg-repo::arsiv_adi .
```

**Oneri:** Bind mount yontemi en iyisi. Files cache calisir, deduplication verimli olur.

### Deduplication Farkli Dizinlerden Calisir mi?

**EVET.** Borg deduplication chunk bazlidir, dosya yolundan bagimsizdir. Ayni icerikli
dosyalar farkli dizinlerden gelse bile deduplicate edilir. Chunk ID'si icerigin
hash'ine dayanir, yola degil.

```
/snapshots/snap1/fs/etc/fstab  \
                                 } -> ayni chunk, tek kopyada saklanir
/snapshots/snap2/fs/etc/fstab  /
```

---

## 3. Mevcut Rsync Snapshot'larini Borg'a Aktarma

### Yontem 1: borg-import Araci (Resmi)

```bash
# Kurulum
pip install --user borg-import

# rsync+hardlink yedeklerini import etme
borg-import rsynchl /snapshots/ /borg-repo

# Ozel prefix ile
borg-import rsynchl --prefix system_ /snapshots/ /borg-repo
```

**Not:** borg-import her snapshot dizini icin ayri bir Borg arsivi olusturur ve
timestamp'i dizin adindan cikarir.

### Yontem 2: Manuel (Bizim format icin daha uygun)

```bash
#!/bin/bash
# migrate-to-borg.sh

BORG_REPO="/borg-repo"
SNAPSHOT_DIR="/snapshots"

# Borg repo olustur (henuz yoksa)
borg init --encryption=none "$BORG_REPO"

# Tum snapshot'lari sirala ve arsivle
for snap_dir in "$SNAPSHOT_DIR"/system_* "$SNAPSHOT_DIR"/full_*; do
    [ -d "$snap_dir/fs" ] || continue

    snap_name=$(basename "$snap_dir")
    echo "Arsivleniyor: $snap_name"

    # Bind mount ile sabit path
    mount --bind "$snap_dir/fs" /mnt/snapshot-current

    borg create \
        --stats \
        --compression zstd,3 \
        --progress \
        "$BORG_REPO::$snap_name" \
        /mnt/snapshot-current

    umount /mnt/snapshot-current
    echo "$snap_name arsivlendi."
done

echo "Migrasyon tamamlandi."
borg list "$BORG_REPO"
borg info "$BORG_REPO"
```

### Deduplication Migrasyon Sirasinda Calisir mi?

**EVET.** Ayni repository'ye eklenen tum arsivler arasinda deduplication aktif. Ornek:

```
system_2026-03-08  -> 13GB (ilk arsiv, tamami yazilir)
system_2026-03-09  -> ~500MB (sadece degisen chunk'lar)
system_2026-03-10  -> ~500MB (sadece degisen chunk'lar)
```

---

## 4. Borg Extract — Rsync-Uyumlu Snapshot Olusturma

### Extract ile Korununlar

| Ozellik | Korunuyor mu? | Detay |
|---------|---------------|-------|
| Dosya izinleri (chmod) | EVET | Unix mode/permissions (u/g/o, suid, sgid, sticky) |
| Sahiplik (uid/gid) | EVET | root olarak calistirildiginda tam koruma |
| Symlink'ler | EVET | Symlink olarak saklanir, takip edilmez |
| Hardlink'ler | KISMI | Hardlink iliskileri korunur, ancak hardlink'li symlink'ler ayri symlink olur |
| Ozel dosyalar (device) | EVET | mknod ile geri olusturulur |
| FIFO'lar | EVET | mkfifo ile geri olusturulur |
| xattr/ACL | EVET | Desteklenir |

### Extract Komutu

```bash
# Hedef dizine extract etme
mkdir -p /snapshots/restored_2026-03-08/fs
cd /snapshots/restored_2026-03-08/fs
borg extract /borg-repo::system_2026-03-08_14-30-00

# Belirli dosyalari extract etme
borg extract /borg-repo::system_2026-03-08_14-30-00 etc/fstab

# Dry-run ile test
borg extract --dry-run --list /borg-repo::system_2026-03-08_14-30-00
```

### GRUB-Bootable Snapshot Olarak Kullanilabilir mi?

**EVET**, su kosullarla:
1. `borg extract` root olarak calistirilmali (uid/gid korunmasi icin)
2. Extract sonrasi `info.conf` dosyasi olusturulmali (snapshot-manager formatina uygun)
3. GRUB menusunde gorulmesi icin `update-grub` calistirilmali

```bash
# Borg'dan GRUB-bootable snapshot olusturma
RESTORE_DIR="/snapshots/system_2026-03-08_14-30-00"
mkdir -p "$RESTORE_DIR/fs"
cd "$RESTORE_DIR/fs"
borg extract /borg-repo::system_2026-03-08_14-30-00

# info.conf olustur
cat > "$RESTORE_DIR/info.conf" << 'EOF'
TYPE=system
DATE=2026-03-08 14:30:00
DESCRIPTION=Borg arsivinden geri yuklendi
SOURCE=borg
EOF

# GRUB guncelle
update-grub
```

---

## 5. Isimlendirme Stratejisi

### Mevcut Format
```
system_2026-03-08_14-30-00
full_2026-03-08_14-30-00
```

### Borg Arsiv Isimlendirme Onerileri

**Oneri: Ayni formati kullan.** Sebepleri:
- Tutarlilik: rsync snapshot adi = borg arsiv adi
- Kolay eslestirme: Hangi snapshot'in arsivlendigini hemen gorursun
- borg prune uyumlulugu: Prefix filtresi ile `system_` veya `full_` ayirt edilebilir

```bash
# Olusturma
borg create /borg-repo::system_2026-03-08_14-30-00 /mnt/snapshot-current
borg create /borg-repo::full_2026-03-08_14-30-00 /mnt/snapshot-current

# Listeleme
borg list /borg-repo --prefix system_
borg list /borg-repo --prefix full_

# Prune (retention policy)
borg prune /borg-repo \
    --prefix system_ \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 6

borg prune /borg-repo \
    --prefix full_ \
    --keep-daily 3 \
    --keep-weekly 4 \
    --keep-monthly 12
```

### Borg 2.0'da Degisiklik

Borg 2.0'da arsivlerin benzersiz isimleri olma zorunlulugu kaldirildi. Ayni isimde
birden fazla arsiv olabilir. Ancak bizim durumumuzda her arsiv zaten benzersiz timestamp
icerdiginden bu onemli degil.

### Yasak Karakterler

Arsiv adlarinda `/` (slash) kullanilMAZ. Bosluk ve ozel karakterlerden kacinilmali.
Bizim mevcut formatimiz (`system_2026-03-08_14-30-00`) tamamen uyumlu.

---

## 6. Esanli (Concurrent) Islemler

### Borg 1.x (Mevcut kararlı surum)

```
rsync snapshot olusturma + borg create  =  SORUNLU
```

Borg 1.x, `borg create` sirasinda repository'ye **exclusive lock** koyar. Bu durumda:
- Iki `borg create` ayni anda calismaz
- rsync snapshot olusturma Borg'dan bagimsiz calistigi icin sorun yok
- Ancak ayni anda borg create + borg prune calismaz

### Borg 2.0

```
rsync snapshot olusturma + borg create  =  SORUNSUZ
borg create + borg create               =  SORUNSUZ (paralel)
borg create + borg check                =  SORUNLU
borg create + borg compact              =  SORUNLU
```

### Bizim Icin Pratik Cozum

```bash
# rsync ve borg ayni anda calisabilir (farkli islemler)
# Ama serialize etmek daha guvenli:

# snapshot-manager icinde:
create_snapshot() {
    rsync_snapshot    # 1. rsync ile snapshot al
    archive_to_borg   # 2. borg ile arsivle (sirali)
}

# Veya flock ile mutex:
(
    flock -n 200 || { echo "Borg zaten calisiyor"; exit 1; }
    borg create ...
) 200>/var/lock/snapshot-borg.lock
```

**Oneri:** rsync ve borg bagimsiz islemlerdir, ayni anda calisabilirler. Ancak
iki borg islemi (create + prune gibi) serialize edilmeli.

---

## 7. Hata Senaryolari

### Borg Create Yarim Kalirsa

**Repository durumu: GUVENLI**

```
Senaryo                    | Sonuc
---------------------------|--------------------------------------------
Ctrl+C / SIGTERM           | Checkpoint arsivi kalir, repo guvenli
Disk dolu                  | Segment dosyasi silinir, alan geri kazanilir
Elektrik kesintisi         | borg check ile dogrulama gerekir
```

**Checkpoint mekanizmasi:**
- Her 5 dakikada bir `arsiv_adi.checkpoint` arsivi olusturulur
- Yarim kalan islemden sonra tekrar `borg create` calistirinca checkpoint'tan devam eder
- Basarili yedeklemeden sonra checkpoint otomatik silinir (`borg prune` ile)

```bash
# Yarim kalan islemden sonra:
borg break-lock /borg-repo        # Kilitli kalmissa
borg create /borg-repo::arsiv_adi /mnt/snapshot-current  # Tekrar calistir

# Disk dolu durumunda:
borg delete /borg-repo::arsiv_adi.checkpoint  # Yer ac
borg compact /borg-repo                        # Disk alaini geri kazan
```

### Borg Extract Yarim Kalirsa

**Hedef dizin durumu: KULLANILMAZ OLABILIR**

- Kismi extract = eksik dosyalar
- Borg extract mevcut dosyalari silerek uzerine yazar
- `--continue` flag'i ile devam ettirilebilir (yeni surumler)

```bash
# Guvenli extract yontemi:
# 1. Gecici dizine extract et
mkdir -p /tmp/borg-extract
cd /tmp/borg-extract
borg extract /borg-repo::arsiv_adi

# 2. Basariliysa hedef dizine tasi
mv /tmp/borg-extract /snapshots/restored_snapshot/fs

# Alternatif: borg mount + rsync (en guvenli)
borg mount /borg-repo::arsiv_adi /mnt/borg-mount
rsync -avH /mnt/borg-mount/ /snapshots/restored_snapshot/fs/
borg umount /mnt/borg-mount
```

### Disk Dolu Sirasinda Kurtarma

```bash
# 1. Lock'u kaldir
borg break-lock /borg-repo

# 2. Checkpoint'lari sil (yer ac)
borg delete /borg-repo::*.checkpoint 2>/dev/null

# 3. Compact ile disk alani geri kazan
borg compact /borg-repo

# 4. Borg check ile dogrula
borg check /borg-repo
```

---

## 8. Alan Hesaplamasi

### Mevcut Durum (rsync+hardlink)

```
3 rsync snapshot (ornek):
  system_2026-03-08  ~13GB (full copy)
  system_2026-03-09  ~500MB (sadece degisen dosyalar, geri kalani hardlink)
  system_2026-03-10  ~500MB (sadece degisen dosyalar, geri kalani hardlink)
  -----------------------------------------
  Toplam disk:       ~14GB  (hardlink sayesinde)
```

### Rsync+Hardlink'in Sinirlamasi

Hardlink yontemi su durumlarda **tum dosyayi yeniden kopyalar**:
- Dosyanin 1 byte'i bile degisse -> tamamen yeni kopya
- Sadece metadata degisse (permission, ownership) -> tamamen yeni kopya
- Dosya yolu degisse (rename) -> tamamen yeni kopya

### Borg ile Karsilastirma

```
20 arsiv (ayni icerik, Borg ile):
  Ilk arsiv:          ~13GB (sikistirilmis: ~8-10GB, zstd ile)
  Sonraki 19 arsiv:   ~200-500MB/arsiv (sadece degisen chunk'lar)
  -----------------------------------------
  Tahmini toplam:     ~15-20GB (20 arsiv icin)

20 snapshot (rsync+hardlink ile):
  Ilk snapshot:       ~13GB
  Sonraki 19:         ~500MB-1GB/snapshot (degisen dosyalar)
  -----------------------------------------
  Tahmini toplam:     ~23-32GB (20 snapshot icin)
```

### Hibrit Model Alan Tahmini

```
Sicak katman (rsync+hardlink): 3 snapshot   = ~14GB
Soguk katman (borg repo):      20 arsiv     = ~15-20GB
                                            -----------
Toplam:                                      ~29-34GB

vs. Tumu rsync+hardlink (20 snapshot):       ~23-32GB
vs. Tumu borg (20 arsiv):                    ~15-20GB
```

**Sonuc:** Hibrit model biraz daha fazla alan kullanir, ama avantajlari:
- Sicak katman: Aninda erisim, GRUB boot, hizli restore
- Soguk katman: Sikistirilmis, uzun sure saklama, deduplication
- Borg'un sikistirma avantaji buyuk dosyalarda (log, database) belirginlesir

---

## 9. Performans Degerlendirmesi

### Yerel Snapshot Dizini vs Canli Filesystem

| Ozellik | Canli Filesystem | Snapshot Dizini |
|---------|-----------------|-----------------|
| Tutarlilik | Dosyalar degisebilir | Sabit (frozen state) |
| Hiz | Degisen dosyalar icin yavaslayabilir | Tahmin edilebilir |
| Lock gereksinimi | Uygulamalar calisirken risk | Risk yok |
| Tavsiye | Cok buyuk sistemlerde sorunlu | **Onerilir** |

**Snapshot dizininden arsivleme kesinlikle daha guvenli ve tutarli.**

### Files Cache Optimizasyonu

```bash
# SORUN: Her snapshot farkli dizinde -> files cache ise yaramaz
# /snapshots/system_2026-03-08/fs/etc/passwd  (1. arsiv)
# /snapshots/system_2026-03-09/fs/etc/passwd  (2. arsiv)
# Borg bunlari farkli dosya olarak gorur (path degismis)

# COZUM 1: Bind mount (EN IYI)
mount --bind /snapshots/system_2026-03-09/fs /mnt/snapshot-current
borg create /borg-repo::system_2026-03-09 /mnt/snapshot-current
# -> files cache "/mnt/snapshot-current/etc/passwd" olarak kayit tutar
# -> sonraki arsivlerde degismemis dosyalar ATLANIR (cok hizli)

# COZUM 2: Files cache devre disi (yavaş ama calisir)
borg create --files-cache disabled /borg-repo::arsiv_adi /snapshots/.../fs/
# -> tum dosyalar okunur ama deduplication yine calisir (chunk seviyesinde)
# -> sadece files cache atlanir, extra I/O olur

# COZUM 3 (borg 1.x): Files cache modlari
# ctime,size,inode (varsayilan)
# mtime,size (daha az false positive)
# size (en hizli ama riskli)
# disabled (tum dosyalari oku)
borg create --files-cache mtime,size /borg-repo::arsiv_adi /mnt/snapshot-current
```

### Chunker Parametreleri

```bash
# Varsayilan chunker parametreleri:
# CHUNK_MIN_EXP = 19  (min 512 KiB)
# CHUNK_MAX_EXP = 23  (max 8 MiB)
# HASH_MASK_BITS = 21 (hedef ~2 MiB)

# Buyuk dosyalar icin (VM disk, database):
borg create --chunker-params buzhash,14,23,16,4095 ...
# Daha kucuk chunk = daha iyi dedup, daha fazla RAM

# Kucuk dosyalar (config, script):
# Varsayilan parametreler uygundur, degistirmeye gerek yok

# Bizim durum icin: Varsayilan parametreler iyi.
# System snapshot'lari cogunlukla kucuk dosyalar icerir.
```

---

## 10. Boot-Time Borg Restore

### Secenek A: Initramfs'den Borg Calistirma

**Teknik olarak mumkun ama ONERILMEZ.**

Sorunlar:
- Borg standalone binary: **~27 MB** (initramfs'e eklenecek)
- Python runtime gerektirir (standalone binary icinde gomulu)
- `/tmp` alanina ihtiyac duyar (unpack icin)
- Initramfs boyutunu onemli olcude arttirir
- Boot suresi uzar

```bash
# Borg binary boyutu kontrol
ls -lh /usr/bin/borg
# veya standalone: borg-linux-glibc231-x86_64 = ~27 MB
```

### Secenek B: Pre-Extract (ONERILIR)

```
[Borg Arsivi] --borg extract--> [rsync Snapshot] --restore.sh--> [Canli Sistem]
```

Bu yaklasim:
1. Borg'dan snapshot'i onceden extract et
2. Mevcut `snapshot-restore` script'i ile geri yukle (PID 1)
3. GRUB menusune otomatik eklenir
4. Borg'a bagimsiz, mevcut altyapi ile calisir

```bash
# Borg'dan snapshot geri yukleme workflow:
# 1. Arsiv listele
borg list /borg-repo

# 2. Hedef dizine extract et
mkdir -p /snapshots/system_2026-03-08_14-30-00/fs
cd /snapshots/system_2026-03-08_14-30-00/fs
borg extract /borg-repo::system_2026-03-08_14-30-00

# 3. info.conf olustur
cat > /snapshots/system_2026-03-08_14-30-00/info.conf << EOF
TYPE=system
DATE=2026-03-08 14:30:00
DESCRIPTION=Borg arsivinden geri yuklendi
SOURCE=borg
EOF

# 4. GRUB guncelle -> Snapshot menude gorunur
update-grub

# 5. Reboot -> GRUB'dan snapshot sec -> restore.sh calisir
```

### Secenek C: Borg Mount + Rsync (Alternatif)

```bash
# FUSE mount ile borg arsivini baglama
borg mount /borg-repo::system_2026-03-08_14-30-00 /mnt/borg-mount

# rsync ile snapshot dizinine kopyalama
rsync -avH --progress /mnt/borg-mount/ /snapshots/system_2026-03-08_14-30-00/fs/

borg umount /mnt/borg-mount
```

Bu yontem:
- Yarim kalma durumunda rsync ile devam ettirilebilir
- Buyuk arsivler icin daha guvenli
- Ancak FUSE overhead nedeniyle daha yavas

---

## Genel Oneriler

### Mimari Karar

```
                    snapshot-manager
                    /              \
           [Sicak Katman]    [Soguk Katman]
          rsync+hardlink      Borg Repo
          Son 3 snapshot      20+ arsiv
          GRUB bootable       Sikistirilmis
          Aninda erisim       Deduplication
                |                  |
                v                  v
          Hizli restore      Uzun sure saklama
          (PID 1 script)     (borg extract ile)
```

### Uygulama Plani

1. **Faz 1:** `borg init` ve `borg create` entegrasyonu
   - Config'e `BORG_REPO` parametresi ekle
   - `snapshot-manager archive` komutu ekle
   - Bind mount pattern ile files cache optimizasyonu

2. **Faz 2:** Otomatik arsivleme
   - Snapshot silme oncesi otomatik borg archive
   - `borg prune` ile eski arsivleri temizle
   - Systemd timer ile periyodik arsivleme

3. **Faz 3:** Geri yukleme
   - `snapshot-manager restore-from-borg` komutu
   - GUI'ye borg arsiv listesi ekleme
   - GRUB menusune "Borg'dan Geri Yukle" secenegi

### Config Ornegi (snapshot-manager.conf'a eklenecek)

```bash
# Borg Archival Backend
# =====================

# Borg repository yolu (bos = devre disi)
BORG_REPO=""

# Borg sifreleme (none, repokey, repokey-blake2)
BORG_ENCRYPTION=none

# Borg sikistirma (none, lz4, zstd, zstd,3, zlib, lzma)
BORG_COMPRESSION=zstd,3

# Rsync snapshot silmeden once borg'a arsivle (true/false)
BORG_ARCHIVE_BEFORE_DELETE=true

# Borg retention policy
BORG_KEEP_DAILY=7
BORG_KEEP_WEEKLY=4
BORG_KEEP_MONTHLY=12
BORG_KEEP_YEARLY=2
```

---

## Kaynaklar

- [borg-import (GitHub)](https://github.com/borgbackup/borg-import)
- [borgsnap (GitHub)](https://github.com/scotte/borgsnap)
- [rsnapshot/rsync+hardlinks importer tartismasi](https://github.com/borgbackup/borg/issues/1754)
- [Borg FAQ](https://borgbackup.readthedocs.io/en/stable/faq.html)
- [Borg Create Dokumantasyonu](https://borgbackup.readthedocs.io/en/stable/usage/create.html)
- [Borg Extract Dokumantasyonu](https://borgbackup.readthedocs.io/en/stable/usage/extract.html)
- [Borg Internals - Deduplication](https://borgbackup.readthedocs.io/en/stable/internals.html)
- [Borg Extract Permissions Issue #2337](https://github.com/borgbackup/borg/issues/2337)
- [Borg Concurrent Access](https://borgbackup.readthedocs.io/en/stable/usage/lock.html)
- [Remote backups with Borg and rsync (Blog)](https://jstaf.github.io/posts/backups-with-borg-rsync/)
- [Syncing and Backups with Rsync and Borg (Blog)](https://dizzard.net/articles/borg_rsync/article.html)
- [Rethinking my backups (Blog)](https://strugglers.net/posts/2025/rethinking-my-backups/)
- [Backup speed benchmark: rsync vs borg vs restic vs kopia](https://grigio.org/backup-speed-benchmark/)
- [Borg Installation - Standalone Binary](https://borgbackup.readthedocs.io/en/stable/installation.html)
- [Restarting interrupted borg extract](https://github.com/borgbackup/borg/discussions/6654)
