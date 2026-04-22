# Bot Signal Saham

Bot ini scan saham IHSG, pilih kandidat `BUY` dan `WATCH`, lalu kirim ringkasan ke Telegram.

## Setup

1. Pastikan Python 3 sudah terpasang.
2. Install dependency yang dibutuhkan.
3. Isi file `.env` dengan `BOT_TOKEN` dan `CHAT_ID`.

## Mode Jalan

### Jalan terus

Default-nya bot akan jalan terus dan pakai mode intraday.

```bash
python bot_signal_saham.py
```

### Scan sekali

Kalau mau cek hasil satu kali saja:

```bash
python bot_signal_saham.py --once
```

### Scan loop intraday

Kalau mau pakai refresh cepat:

```bash
python bot_signal_saham.py --loop --intraday --interval 1
```

### Backtest

Untuk lihat performa scoring:

```bash
python bot_signal_saham.py --backtest
```

## Auto Start Windows

Kalau mau tinggal jalan saat dibuka, pakai:

```bash
.\start_bot.bat
```

Di PowerShell, pakai `.\` supaya command dari folder saat ini bisa dikenali.

## Deploy ke Vercel

Bot bisa dijalankan sebagai Vercel Function lewat cron.

Endpoint cepat:

- Scan harian otomatis: `/api?mode=daily&notify=changes&bootstrap=1`
- Health-check ringkas: `/api?action=health`
- Health-check verbose: `/api?action=health&view=verbose`
- Test Telegram: `/api?action=test-telegram`
- Scan manual intraday: `/api?mode=intraday&notify=changes&bootstrap=1`

Contoh pakai browser / curl:

```bash
curl "https://nama-project.vercel.app/api?action=health"
```

Health-check sekarang mendukung dua mode:
- `compact` default: `ready` + `summary`
- `verbose`: `ready` + `summary` + `components`

Notifikasi perubahan saham:

```bash
/api?mode=daily&notify=changes&bootstrap=1
```

Catatan penting:
- Vercel Cron Jobs memakai timezone UTC.
- Plan Hobby hanya mendukung cron sekali sehari.
- Config default di repo ini sekarang menjalankan `/api?mode=daily&notify=changes&bootstrap=1` pada `0 2 * * *` UTC, kira-kira jam 09:00 WIB.
- Untuk scan intraday per menit, biasanya perlu Pro atau plan di atasnya.
- Jika kamu set `CRON_SECRET`, Vercel akan kirim header `Authorization: Bearer <secret>`.
- Untuk cek Telegram benar-benar terkirim, buka endpoint `action=test-telegram`.
- Untuk notifikasi perubahan saham, `bootstrap=1` menyimpan state awal tanpa spam saat run pertama.
- Kamu tidak perlu klik domain setelah deploy; cron Vercel yang akan memanggil function otomatis.
- `action=health` menampilkan status env, cache, dan runtime supaya troubleshooting lebih cepat.
- `action=health` sekarang dibuat ringkas untuk dashboard, tapi tetap memuat detail komponen inti.
- `action=health&view=verbose` menampilkan detail komponen penuh.
- `action=test-telegram` dipakai buat verifikasi pengiriman pesan Telegram dari Vercel.

File yang dipakai untuk Vercel:
- `api/scan.py`: endpoint scan
- `api/index.py`: entrypoint Vercel
- `vercel.json`: konfigurasi cron
- `requirements.txt`: dependency Python

### Checklist Deploy

1. Pastikan project sudah ada di Git repository.
2. Isi `.env` lokal dengan `BOT_TOKEN`, `CHAT_ID`, dan kalau perlu `CRON_SECRET`.
3. Buat project baru di Vercel dan connect ke repository ini.
4. Set environment variables di Vercel:
   - `BOT_TOKEN`
   - `CHAT_ID`
   - `CRON_SECRET` jika endpoint mau diamankan
5. Push perubahan ke branch yang dideploy.
6. Cek deployment berhasil dan endpoint `/api` bisa dibuka.
7. Kalau pakai `CRON_SECRET`, tes dengan header:

```bash
Authorization: Bearer <CRON_SECRET>
```

8. Pastikan cron job aktif di dashboard Vercel.
9. Pantau logs Vercel untuk memastikan Telegram terkirim dan sinyal tidak spam.
10. Jika cron per menit tidak diizinkan di plan yang dipakai, turunkan frekuensi atau upgrade plan.

## File Penting

- `bot_signal_saham.py`: entrypoint CLI
- `scanner.py`: analisis dan runtime scan
- `backtest.py`: backtest sederhana
- `telegram.py`: kirim Telegram dan simpan state anti-spam
- `config.py`: konstanta dan loader `.env`
- `api/scan.py`: endpoint Vercel
- `.env`: konfigurasi Telegram

## Catatan

- `BUY SECTION` hanya menampilkan 1-3 kandidat terkuat.
- Telegram hanya dikirim saat sinyal berubah agar tidak spam.
- Data intraday lebih cocok untuk mode loop.
