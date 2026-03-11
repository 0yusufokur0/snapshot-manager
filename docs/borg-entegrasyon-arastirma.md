# Borg Backup Entegrasyon Arastirmasi

**Tarih:** 2026-03-10
**Mevcut sistem:** rsync + hardlink snapshot, GRUB restore entegrasyonu, ext4, NVMe
**Snapshot diski:** /dev/nvme0n1p1 (469GB, 62GB dolu, 384GB bos)
**Guncel snapshot boyutlari:** system ~11GB, full ~14GB, toplam ~65GB (6 snapshot)

---

## 1. Borg + rsync Hibrit Calisma Duzeni

### Konsept
Son 2-3 rsync+hardlink snapshot'i GRUB restore icin sikistirilmamis tutulur, eski snapshot'lar otomatik olarak Borg repo'suna arsivlenip rsync kopyalari silinir.

### Uygulanabilirlik
Bu yaygin bir pattern. Birden fazla kullanici ve proje (borgsnap gibi) bu yaklasimi kullaniyor. Borg'un resmi `borg-import` araci ozellikle rsync+hardlink yedeklerini Borg formatina donusturmek icin yazilmis:

```bash
pip install borg-import
borg-import rsynchl /mnt/nvme0n1p1/snapshots/ /mnt/nvme0n1p1/borg-repo
```

### Onerilen akis
1. `snapshot-manager create` calisir (rsync+hardlink, her zamanki gibi)
2. Snapshot sayisi 3'u gectiginde, en eski snapshot Borg'a arsivlenir:
   ```bash
   borg create /mnt/nvme0n1p1/borg-repo::system_{timestamp} /mnt/nvme0n1p1/snapshots/system_ESKI/
   ```
3. Borg arsivlemesi basarili olursa, eski rsync snapshot silinir
4. Son 2-3 snapshot her zaman rsync+hardlink olarak kalir (GRUB restore icin)

### Dikkat edilmesi gerekenler
- Borg repo'su ile rsync snapshot'lari AYNI DISK uzerinde olacak (bkz. Madde 4)
- Borg single-threaded calisir, arsivleme sirasinda diger islemler yavaslayabilir
- `borg create` sirasinda exclusive lock gerekli degildir, ama `borg compact` ve `borg check` exclusive lock ister
- Borg 1.x ve 2.x repo formatlari uyumsuz, versiyon secimi onemli (bkz. Madde 6)

---

## 2. Borg Performansi: NVMe ext4 Uzerinde

### Ilk yedekleme (initial backup) — ~11GB system snapshot
- Borg CRUD benchmark sonuclari: rastgele veri icin ~142 MB/s, sifir veri icin ~449 MB/s
- **Gercekci tahmin:** 11GB system snapshot icin ilk yedekleme ~1-2 dakika (NVMe lokal, sikistirma acik)
- Borg single-threaded calistigi icin NVMe'nin tam hizini (1400+ MB/s) kullanamaz, ~130 MB/s civarinda darbogazlanir

### Artimsal yedekleme (incremental)
- Deduplication sayesinde sadece degisen bloklar yazilir
- Gunluk degisim genelde birka yuz MB, artimsal yedekleme **saniyeler icinde** tamamlanir
- Borg %70-85 deduplication orani saglar (sistem yedekleri icin cok etkili)

### Sikistirma etkileri
- `zstd` (varsayilan Borg 1.4): hiz/oran dengesi iyi
- `lz4`: en hizli, daha az sikistirma
- `zstd,3`: system snapshot icin iyi denge, ~%40-50 alan tasarrufu

---

## 3. Borg'dan Geri Yukleme Hizi

### Dogrudan extract (borg extract)
- Lokal NVMe'de ~100-130 MB/s extract hizi beklenir (Borg darbogazli, disk degil)
- **11GB system snapshot icin: ~1.5-2 dakika**
- `borg extract` kullanmak, `borg mount` + rsync'den daha hizlidir

### FUSE mount (borg mount)
- Daha yavas ama interaktif dosya secimi mumkun
- Buyuk geri yuklemeler icin onerilmez

### GRUB restore ile karsilastirma
- Mevcut rsync snapshot'tan restore: dosya kopyalama hizinda (~500+ MB/s NVMe)
- Borg'dan restore: once extract (~2dk) + sonra dosyalari yerine kopyalama
- **Sonuc:** GRUB restore icin rsync snapshot'lari tutmak dogru karar. Borg sadece arsiv icin kullanilmali.

---

## 4. Borg Repo: Ayni Disk mi, Harici Disk mi?

### Mevcut durum
- Snapshot diski: /dev/nvme0n1p1 (469GB, 62GB kullaniliyor, 384GB bos)
- Root diski: /dev/nvme0n1p2 (ayri NVMe)
- Snapshot'lar zaten root'tan farkli bir disk/partition uzerinde

### Ayni disk uzerinde Borg repo (onerilir MI?)
**Senaryonuz icin UYGUN:**
- Snapshot'lariniz zaten root'tan ayri bir diskte. Borg repo'sunu da ayni snapshot diskine koymak mantikli cunku:
  - Asil amac: disk arizasina karsi koruma degil, **alan tasarrufu** (dedup + sikistirma)
  - 384GB bos alan var, Borg repo icin fazlasiyla yeterli
  - Ayni NVMe uzerinde olunca I/O hizi maksimum
- Disk arizasina karsi koruma istiyorsaniz, **ek olarak** uzak/harici bir Borg repo olusturun

### Alan birakmak onemli
- Borg'un calismasi icin her zaman birka GB bos alan olmali
- `borg compact` gecici olarak ekstra alan kullanir
- Oneri: diskin %90'indan fazlasini doldurmamaya dikkat edin

---

## 5. Borg Bakim Islemleri

### borg compact
- **Ne yapar:** Silinen arsivlerin biraktigi bos alani geri kazanir
- **Ne siklikta:** Her yedeklemede degil, **ayda 1 kez** yeterli (veya alan darliginda)
- **Etki:** Orta duzeyde I/O, exclusive lock gerektirir (bu sirada baska borg islemi yapilamaz)
- **Sizin icin:** 11GB snapshot'lar ve ayda birka arsivleme ile compact islemi dakikalar icerisinde biter

### borg check
- **Ne yapar:** Repo butunlugunu dogrular (checksum kontrolu)
- **Ne siklikta:** **Ayda 1 kez** onerilir
- **Etki:** Tum chunk'larin checksum'ini hesaplar, CPU ve I/O yogun
- **Oneri:** `--max-duration 300` ile 5 dakikalik artirimsal kontrol yapilabilir (buyuk repo'lar icin)
- **Sizin icin:** Kucuk repo boyutuyla (<50GB) tam kontrol bile birka dakika surer

### Bakim plani onerisi
```bash
# Haftalik cron (Pazar gece 03:00)
0 3 * * 0 borg compact /mnt/nvme0n1p1/borg-repo && borg check /mnt/nvme0n1p1/borg-repo
```

---

## 6. Borg 1.x vs 2.x — Hangisi Kullanilmali?

### Kesin cevap: **Borg 1.4.x** (uretim icin)

| Ozellik | Borg 1.4.x | Borg 2.x |
|---------|-----------|---------|
| Durum | **Stable** (son surum: 1.4.3, 2025-12-02) | **Beta** (hala gelistirme asamasinda) |
| Uretim kullanimi | EVET | **HAYIR** (resmi dokumantasyon uyariyor) |
| Ubuntu 24.04 paketi | `apt install borgbackup` ile gelir | Manuel kurulum gerekir |
| Performans | Yeterli | %5-20 daha hizli |
| Repo formati | 1.x | 2.x (uyumsuz) |

**Borg 2.x dokumantasyonundan direkt alinti:**
> "DO NOT USE BORG2 FOR YOUR PRODUCTION BACKUPS"

### Oneri
- Simdi Borg 1.4.x kurun
- Borg 2.0 stable cikarsa (2026 sonlari veya 2027?), `borg transfer` ile gecis yapin

---

## 7. Alternatif: tar + zstd ile Sikistirma

### Konsept
En yeni 2-3 snapshot rsync+hardlink olarak kalir, eski snapshot'lar `tar --zstd` ile sikistirilir.

### Beklenen alan tasarrufu
- zstd varsayilan seviye (3): **%40-50 sikistirma** (sistem dosyalari icin)
- 11GB system snapshot → **~5.5-6.5GB** tar.zst dosyasi
- 14GB full snapshot → **~7-8.5GB** tar.zst dosyasi

### Avantajlar
- **Cok basit:** Borg gibi ek yazilim gerektirmez
- **Hizli:** zstd sikistirma 11GB icin ~15-30 saniye (NVMe)
- **GRUB entegrasyonu etkilenmez** (son snapshot'lar aynen kalir)
- **Geri yukleme basit:** `tar --zstd -xpf arsiv.tar.zst -C /hedef/`

### Dezavantajlar
- **Deduplication YOK:** Her arsiv bagimsiz, ortak dosyalar tekrarlanir
- **Artimsal yedekleme YOK:** Her seferinde tam arsiv olusur
- Borg'a gore daha fazla alan kullanir (dedup olmadigi icin)

### Karsilastirma: 10 snapshot arsivi (system)

| Yontem | Tahmini toplam boyut |
|--------|---------------------|
| rsync+hardlink (mevcut) | ~65GB (6 snapshot, hardlink sayesinde) |
| tar+zstd (her biri bagimsiz) | ~55-65GB (10 arsiv x 5.5-6.5GB) |
| Borg (dedup + zstd) | **~15-20GB** (dedup sayesinde) |

**Sonuc:** tar+zstd, hardlink'li rsync'e gore neredeyse hic tasarruf saglamaz (hatta daha kotu olabilir cunku hardlink paylasimi kaybolur). **Borg'un asil gucu deduplication'da.**

---

## 8. rsync --compress ve Diger Flag'ler

### rsync -z (--compress)
- **Sadece transfer sirasinda** sikistirma yapar, **hedef dosyayi sikistirmaz**
- Lokal kopyalamada (ayni makine) **hicbir faydasi yok**, sadece CPU harcar
- Sadece ag uzerinden (SSH) transfer icin faydali

### rsync --link-dest (zaten kullaniyorsunuz)
- Degismeyen dosyalar icin hardlink olusturur
- **Bu zaten en etkili rsync tabanli alan tasarrufu yontemidir**
- Mevcut sistemde dogru sekilde kullaniliyor

### rsync ile alan tasarrufu icin baska secenek var mi?
- **Hayir.** rsync dosyalari oldugu gibi kopyalar, sikistirma destegi yoktur (depolama bazinda)
- `--sparse` buyuk seyrek dosyalar icin faydali olabilir ama sistem yedeklerinde etkisi az
- Alan tasarrufu icin ya Borg gibi dedup araci ya da tar+zstd gibi sikistirma gerekir

---

## Genel Degerlendirme ve Oneri

### En iyi strateji: Hibrit rsync + Borg

```
[Son 2-3 snapshot] ──── rsync+hardlink (mevcut, GRUB restore icin)
        │
        ▼ (eski snapshot'lar otomatik arsivlenir)
        │
[Borg repo] ──── dedup + zstd sikistirma (~%70-85 alan tasarrufu)
```

### Uygulama plani
1. `sudo apt install borgbackup` (Borg 1.4.x)
2. Borg repo olustur: `borg init --encryption=none /mnt/nvme0n1p1/borg-repo`
3. `snapshot-manager` icine arsivleme mantigi ekle:
   - Snapshot sayisi > 3 ise en eskisini Borg'a arsivle
   - Arsivleme basarili ise rsync snapshot'i sil
4. Haftalik cron ile `borg compact` + `borg check`

### Beklenen alan kazanimi
- Mevcut: 6 snapshot = ~65GB
- Hedef: 3 rsync snapshot (~33GB) + 10+ Borg arsivi (~15-20GB) = ~50GB
- Uzun vadede (50+ arsiv): rsync ~33GB + Borg ~25-30GB = ~60GB (50 arsiv!)
- **Yani 6 snapshot yerine 50+ arsiv, neredeyse ayni disk alani**

### Neden tar+zstd degil?
- tar+zstd deduplication yapamaz, 10 arsiv = 10x tam boyut
- Borg ile 10 arsiv ≈ 1.5-2x tam boyut (dedup sayesinde)
- Fark cok buyuk, ozellikle uzun vadeli arsivlemede

---

## Kaynaklar

- [Borg FAQ](https://borgbackup.readthedocs.io/en/stable/faq.html)
- [borg-import (rsync hardlink importer)](https://github.com/borgbackup/borg-import)
- [rsnapshot/rsync+hardlinks importer issue](https://github.com/borgbackup/borg/issues/1754)
- [Borg release series](https://www.borgbackup.org/releases/)
- [Borg CRUD benchmarks](https://borgbackup.readthedocs.io/en/stable/usage/benchmark.html)
- [borgbase/benchmarks](https://github.com/borgbase/benchmarks)
- [Borg backup speed issues](https://github.com/borgbackup/borg/issues/7253)
- [borg extract performance](https://github.com/borgbackup/borg/issues/2407)
- [borg compact docs](https://borgbackup.readthedocs.io/en/latest/usage/compact.html)
- [borg check docs](https://borgbackup.readthedocs.io/en/stable/usage/check.html)
- [Restic vs BorgBackup vs Kopia 2025](https://onidel.com/blog/restic-vs-borgbackup-vs-kopia-2025/)
- [BorgBackup in 2025](https://mangohost.net/blog/borgbackup-in-2025-efficient-compression-and-deduplication-for-linux-servers/)
- [Borg multi-thread discussion](https://github.com/borgbackup/borg/discussions/6958)
- [Syncing and Backups with Rsync and Borg](https://dizzard.net/articles/borg_rsync/article.html)
- [Borg Arch Wiki](https://wiki.archlinux.org/title/Borg_backup)
