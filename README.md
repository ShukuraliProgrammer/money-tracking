# Karta nazoratchi

Debit kartalardagi kirim va chiqimlarni kuzatadigan Telegram bot. Karta xabarini botga tashlaysiz, bot uchta savol beradi va oy oxirida hamma kartalar bo‘yicha hisobot chiqaradi.

```
Siz:  💸 Oplata
      ➖ 54.000,00 UZS
      📍 YANDEX GO
      💳 HUMOCARD *1234
      🕓 12:01 19.11.2026

Bot:  💸 Chiqim aniqlandi:
      Summa: 54 000 UZS · Joy: YANDEX GO · Karta: ****1234 · Vaqt: 19.11.2026 12:01
      Nima uchun qilindi?      [Tahrirlash] [Bekor qilish] [O‘z kartamga o‘tkazma]
Siz:  Taksi — uyga qaytish
Bot:  Qaysi turga kiradi?    [P2P] [Ovqatlanish] [Narsa sotib olish] … [+ Yangi tur]
Bot:  ✅ Saqlandi: 💸 54 000 UZS — YANDEX GO
      🔁 P2P · Asosiy Humo ****1234
```

Xabardagi karta ro‘yxatingizda bo‘lsa, bot uni o‘zi qo‘yadi; «Qaysi kartadan?» savoli faqat karta aniqlanmaganda beriladi.

## Imkoniyatlar

- **Kiritish:** CardXabarBot va HUMOcardbot xabarlari, bank SMS’i (lotin/kirill), oddiy matn («Kamolonda 250 ming so‘m ovqatlandik»), PDF chek, screenshot (AI kaliti sozlangan bo‘lsa), `/add`.
- **Savollar:** nima uchun qilindi (izoh), qaysi turga kiradi va — karta xabardan aniqlanmasa — qaysi kartadan.
- **Hisobot:** `/report` darhol shu oyning hamma kartalar bo‘yicha hisobotini ko‘rsatadi; davr, karta va tur filtri ostidagi tugmalarda. Yig‘indilar, kartalar va turlar bo‘yicha taqsimot, eng katta xarajatlar, har bir tranzaksiya izohi bilan ro‘yxat, rasm, CSV.
- **Avtomatik hisobotlar:** har kuni 21:00 da kunlik (matn), har dushanba haftalik va har oyning 1-kuni oylik (rasm + matn). Har biri `/settings` da alohida o‘chiriladi.
- **O‘z kartalar orasidagi o‘tkazma:** hisobotga yozilmaydi. Xulosadagi «O‘z kartamga o‘tkazma» tugmasi bilan, yoki ikkala tomonni tashlasangiz (bir kartadan chiqim, boshqasiga shu summada kirim, orasi 10 daqiqagacha) bot o‘zi sezib so‘raydi. Jo‘natuvchi tomondagi 2% gacha komissiya farqi ham shu juftlik deb olinadi va yozilmaydi.
- **O‘rganish:** bir joy uchun tanlangan tur keyingi safar ⭐ bilan taklif qilinadi.
- **Kartalar va turlar:** bir nechta karta, o‘z turlaringiz.
- **Maxfiylik:** to‘liq karta raqami saqlanmaydi, izoh va asl xabar shifrlanadi, `/settings` orqali hamma ma’lumotni o‘chirish mumkin.

Bot boshqa botlarning xabarlarini o‘zi o‘qimaydi: faqat siz forward qilgan yoki nusxalab yuborgan matn bilan ishlaydi.

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/start` | Botni tanishtirish, profil yaratish |
| `/add` | Qo‘lda tranzaksiya qo‘shish |
| `/cards`, `/addcard` | Kartalar ro‘yxati, yangi karta |
| `/report` | Shu oy hisoboti; tugmalar bilan davr, karta va tur filtri |
| `/stat` | Oxirgi 30 kun va 6 oylik trend |
| `/categories` | Turlar (qo‘shish, o‘chirish) |
| `/export` | CSV fayl |
| `/delete` | Oxirgi tranzaksiyani o‘chirish |
| `/settings` | Vaqt zonasi, valyuta, avtomatik hisobotlar, ma’lumotlarni o‘chirish |
| `/cancel`, `/help` | Joriy amalni bekor qilish, yordam |

## Ishga tushirish

### 1. BotFather

1. Telegram’da [@BotFather](https://t.me/BotFather) ga yozing: `/newbot`.
2. Bot nomi (`Karta nazoratchi`) va username (masalan `karta_nazoratchi_bot`) bering.
3. BotFather bergan tokenni `.env` faylidagi `BOT_TOKEN` ga yozing.
4. Buyruqlar ro‘yxati bot ishga tushganda avtomatik o‘rnatiladi. Xohlasangiz `/setdescription` bilan tavsif qo‘shing.

Bot faqat shaxsiy chatda ishlaydi, guruhlarda javob bermaydi.

### 2. Sozlamalar

```bash
cp .env.example .env
```

Shifrlash kalitini yarating va `.env` dagi `ENCRYPTION_KEY` ga yozing:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Kalitni yo‘qotsangiz, saqlangan izohlar va asl xabarlar o‘qilmaydi. Zaxira nusxasini alohida saqlang.

| O‘zgaruvchi | Standart | Izoh |
|---|---|---|
| `BOT_TOKEN` | — | BotFather tokeni (majburiy) |
| `ENCRYPTION_KEY` | — | Fernet kaliti (majburiy) |
| `POSTGRES_PASSWORD` | — | Docker compose ichidagi PostgreSQL paroli (majburiy; `openssl rand -hex 24`) |
| `DATABASE_URL` | compose o‘zi beradi | Faqat Docker’siz ishga tushirganda: `postgresql+asyncpg://…` |
| `REDIS_URL` | bo‘sh | Berilsa, suhbat holati Redis’da saqlanadi |
| `LLM_PROVIDER` | `none` | `none`, `anthropic` yoki `openai` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_EFFORT` | —, `claude-opus-5-5`, `low` | Claude sozlamalari |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | —, `gpt-5-mini` | OpenAI sozlamalari |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_ATTEMPTS`, `LLM_NOTE_ANALYSIS` | `30`, `3`, `true` | LLM chaqiruvi |
| `DEFAULT_TIMEZONE`, `DEFAULT_CURRENCY`, `LOG_LEVEL` | `Asia/Tashkent`, `UZS`, `INFO` | Yangi foydalanuvchi uchun standartlar |

### 3a. Docker (tavsiya etiladi)

```bash
docker compose up -d --build
```

```bash
docker compose logs -f bot
```

Ma’lumotlar shu compose ichidagi PostgreSQL’da, `postgres_data` nomli volume’da saqlanadi. Baza porti tashqariga ochilmaydi.

Zaxira nusxa olish:

```bash
docker compose exec postgres pg_dump -U moneytrack moneytrack > moneytrack_backup.sql
```

Redis kerak bo‘lsa (suhbat holati uchun): `.env` ga `REDIS_URL=redis://redis:6379/0` yozing va `docker compose --profile redis up -d --build`.

### 3b. Docker’siz (lokal)

Python 3.11 yoki yangiroq va ishlab turgan PostgreSQL kerak. `.env` ga baza manzilini yozing:

```
DATABASE_URL=postgresql+asyncpg://moneytrack:PAROL@localhost:5432/moneytrack
```

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
python -m app.main
```

Ikkala usulda ham baza migratsiyalari ishga tushishda avtomatik bajariladi. Qo‘lda bajarish uchun: `alembic upgrade head`.

## Avtomatik hisobotlar

Vaqtlar foydalanuvchining vaqt zonasi bo‘yicha (`/settings`).

| Hisobot | Qachon | Qaysi davr | Ko‘rinishi |
|---|---|---|---|
| Kunlik | har kuni 21:00 | shu kun | matn: yig‘indi va har bir tranzaksiya izohi bilan |
| Haftalik | dushanba 09:00 | o‘tgan hafta (dushanba–yakshanba) | rasm + matn |
| Oylik | har oyning 1-kuni 09:00 | o‘tgan oy | rasm + matn |

- Rasmda kirim, chiqim, farq va turlar bo‘yicha chiqim ustunlari bor (asosiy valyuta bo‘yicha). Rasm ovozsiz, matn bildirishnoma bilan keladi, shuning uchun bitta signal eshitiladi.
- Har bir hisobot ostidagi tugmalar o‘sha davrning tranzaksiyalar ro‘yxati, rasmi va CSV faylini ochadi. `/report` ichida ham «🖼 Rasm» tugmasi bor.
- Davrda tranzaksiya bo‘lmasa, hisobot yuborilmaydi.
- Bot belgilangan vaqtda ishlamay turgan bo‘lsa, haftalik va oylik hisobot keyingi tekshiruvda (har 30 daqiqada) yuboriladi. Kunlik hisobot faqat o‘sha kuni 21:00–24:00 orasida yuboriladi.
- 21:00 dan keyingi tranzaksiyalar o‘sha kungi kunlik hisobotga kirmaydi, lekin haftalik va oylik hisobotda bo‘ladi.

## Serverga joylash

Domen kerak emas: bot Telegram’dan xabarlarni o‘zi so‘rab oladi, serverga tashqaridan hech kim ulanmaydi.

**1. Repo’ni serverga clone qiling** (Ubuntu yoki Debian):

```bash
git clone https://github.com/ShukuraliProgrammer/money-tracking.git
```

```bash
cd money-tracking
```

**2. Serverni tayyorlang:**

```bash
sudo bash deploy/server-setup.sh
```

Skript Docker’ni o‘rnatadi (bo‘lmasa) va shu papkada `.env` faylini shifrlash kaliti va PostgreSQL paroli bilan yaratadi. Qayta ishga tushirish xavfsiz.

**3. Bot tokenini yozing:**

```bash
nano .env
```

`BOT_TOKEN=` qatoriga @BotFather bergan tokenni qo‘ying. LLM kaliti kabi boshqa sozlamalar ham shu faylga yoziladi (`.env.example` ga qarang).

**4. Ishga tushiring:**

```bash
docker compose up -d --build
```

Keyingi yangilanishlar qo‘lda shunday olinadi:

```bash
git pull && docker compose up -d --build
```

### Avtomatik yangilash (ixtiyoriy)

`.github/workflows/deploy.yml` testlarni ishga tushiradi va o‘tsa, serverga SSH orqali kirib shu ikki buyruqni o‘zi bajaradi: `git pull` va `docker compose up -d --build`. Keyin bot 20 soniya yiqilmay ishlab turganini tekshiradi; yiqilsa, xato bilan tugaydi va oxirgi loglarni ko‘rsatadi. U `main` branchiga push bo‘lganda yoki Actions sahifasidagi **Run workflow** tugmasi bilan ishlaydi.

Yoqish uchun:

1. O‘z kompyuteringizda deploy kalitini yarating:

```bash
ssh-keygen -t ed25519 -N "" -C moneytrack-deploy -f moneytrack_deploy
```

2. Ochiq kalitni (`moneytrack_deploy.pub` mazmunini) serverda o‘z foydalanuvchingizga qo‘shing:

```bash
sudo bash deploy/server-setup.sh "ssh-ed25519 AAAA... moneytrack-deploy"
```

3. GitHub’da sirlarni kiriting (repo → Settings → Secrets and variables → Actions):

| Nomi | Qiymati |
|---|---|
| `DEPLOY_HOST` | server IP manzili |
| `DEPLOY_USER` | repo’ni clone qilgan foydalanuvchi |
| `DEPLOY_SSH_KEY` | `moneytrack_deploy` faylining to‘liq mazmuni |
| `DEPLOY_PATH` | ixtiyoriy: repo papkasi, agar uy papkasidagi `money-tracking` bo‘lmasa |
| `DEPLOY_PORT` | ixtiyoriy: SSH porti, agar 22 bo‘lmasa |

Bot tokeni va boshqa sozlamalar GitHub’da emas, faqat serverdagi `.env` faylida turadi. Sirlar kiritilmagan bo‘lsa, deploy qadami xato bilan to‘xtaydi; testlar baribir ishlaydi.

Eslatmalar:

- **Bitta nusxa.** Bir token bilan bir vaqtda faqat bitta bot ishlashi mumkin. Serverda ishga tushirgach, boshqa joydagi botni to‘xtating (`docker compose down`).
- **Mavjud ma’lumotlar.** Yangi serverda baza bo‘sh boshlanadi. Boshqa PostgreSQL’dan ko‘chirayotgan bo‘lsangiz, `pg_dump` nusxasini tiklang va eski `ENCRYPTION_KEY`’ni ham olib o‘ting; kalit boshqa bo‘lsa, eski izohlar o‘qilmaydi. Eski SQLite bazasi avtomatik ko‘chirilmaydi.
- **Serverda kodni qo‘lda o‘zgartirmang.** Avtomatik yangilash `git pull --ff-only` ishlatadi: serverdagi nusxada commit qilinmagan o‘zgarish bo‘lsa, to‘xtaydi.

## Bazaga ulanish (pgAdmin)

PostgreSQL serverda faqat `127.0.0.1:5432` da ochiq, internetdan ko‘rinmaydi. Kompyuteringizdagi pgAdmin unga SSH tunnel orqali ulanadi.

pgAdmin → **Register → Server**:

| Bo‘lim | Maydon | Qiymat |
|---|---|---|
| General | Name | Karta nazoratchi |
| Connection | Host name/address | `127.0.0.1` |
| Connection | Port | `5432` |
| Connection | Maintenance database | `moneytrack` |
| Connection | Username | `moneytrack` |
| Connection | Password | serverdagi `.env` faylidagi `POSTGRES_PASSWORD` |
| SSH Tunnel | Use SSH tunneling | yoqilgan |
| SSH Tunnel | Tunnel host | server IP manzili |
| SSH Tunnel | Tunnel port | `22` |
| SSH Tunnel | Username | serverga kiradigan foydalanuvchingiz |
| SSH Tunnel | Authentication | serverga qanday kirsangiz shunday: parol yoki kalit fayli |

Parolni ko‘rish (serverda, repo papkasida):

```bash
grep POSTGRES_PASSWORD .env
```

pgAdmin’ning SSH tunneli ishlamasa, tunnelni o‘zingiz oching va pgAdmin’da `localhost`, port `5433` ga ulaning (SSH Tunnel bo‘limini o‘chirib):

```bash
ssh -N -L 5433:127.0.0.1:5432 FOYDALANUVCHI@SERVER_IP
```

Bilib qo‘ying:

- `transactions` jadvalidagi `raw_text`, `user_note` va `ai_summary` ustunlari shifrlangan, pgAdmin’da `gAAAA…` ko‘rinishida chiqadi. Qolgan ustunlar (summa, joy, sana, karta) ochiq.
- Serverda 5432 port band bo‘lsa, `.env` ga `POSTGRES_PORT=5433` yozing va `docker compose up -d` qiling.
- Bazani internetga to‘g‘ridan-to‘g‘ri ochish (`POSTGRES_BIND=0.0.0.0`) tavsiya etilmaydi; shunday qilsangiz, firewall bilan faqat o‘z IP manzilingizga ruxsat bering.

## Xabar qanday o‘qiladi

1. **Tozalash.** 13–19 xonali karta raqamlari `****1234` ko‘rinishiga keltiriladi. SMS kod, parol, PIN yoki CVV ga o‘xshash xabar umuman qayta ishlanmaydi.
2. **Qoidalar (regex).** `app/services/parser.py` summa, valyuta, kirim/chiqim, joy, karta, sana va manbani ajratadi. CardXabar, HUMO va bank SMS shu bosqichda, LLM’siz o‘qiladi. Balans («💰», «Qoldiq», «Dostupno») summa deb olinmaydi.
3. **LLM (ixtiyoriy zaxira).** Qoidalar yetarli bo‘lmasa (odatda erkin matn) va `LLM_PROVIDER` sozlangan bo‘lsa, yashirilgan matn LLM’ga yuboriladi. LLM qaytargan karta raqami yoki sana matnda bo‘lmasa, qabul qilinmaydi.
4. **So‘rash.** Summa, kirim/chiqim yoki sana aniqlanmasa, bot so‘raydi. Matnda sana bo‘lmasa-yu, xabar forward qilingan bo‘lsa, asl xabar vaqti olinadi; joriy vaqt o‘zidan-o‘zi qo‘yilmaydi.

Yangi format qo‘shish: namunani `tests/samples.py` ga, kutilgan natijani `tests/test_parser.py` ga yozing, keyin `parser.py` dagi kalit so‘zlarni to‘ldiring.

> Parser qoidalari CardXabar va HUMO xabarlarining ma’lum ko‘rinishlari asosida yozilgan, haqiqiy xabarlar to‘plamida tekshirilmagan. Bot biror xabarni noto‘g‘ri o‘qisa, o‘sha xabarni (raqamlarini yashirib) namuna sifatida qo‘shing.

### LLM

- Promptlar: `app/services/llm.py` (`PARSE_SYSTEM_PROMPT`, `NOTE_SYSTEM_PROMPT`).
- Javob JSON sxema bo‘yicha so‘raladi; noto‘g‘ri JSON kelsa `LLM_MAX_ATTEMPTS` martagacha qayta so‘raladi, bo‘lmasa qoidalar natijasi ishlatiladi.
- Anthropic uchun standart model `claude-opus-5-5`, `effort=low`. Arzonroq variant kerak bo‘lsa `ANTHROPIC_MODEL=claude-haiku-5-5` qiling. Opus/Sonnet/Fable modellarida rad etilgan so‘rov server tomonda zaxira modelga o‘tadi (`fallbacks="default"`).
- **Screenshot** faqat LLM orqali o‘qiladi (`PARSE`/`SCREENSHOT_SYSTEM_PROMPT`): rasm provayderga yuboriladi, u tranzaksiyani va rasmdagi matnni qaytaradi, keyin natija matnli xabar bilan bir xil tekshiruvdan o‘tadi (karta raqami yashiriladi, SMS kodli rasm rad etiladi). `LLM_PROVIDER=none` bo‘lsa, bot rasm o‘rniga matn so‘raydi. Bitta rasmda bitta tranzaksiya o‘qiladi, hajmi 5 MB gacha. Rasm oddiy holda ham, fayl sifatida ham yuborilishi mumkin (JPEG, PNG, WebP, GIF; BMP va TIFF o‘zi o‘giriladi; HEIC faylini rasm sifatida yuborish kerak).
- **O‘tkazma cheki** (masalan, Uzum Bank PDF’i)da jo‘natuvchi va qabul qiluvchi kartasi bo‘ladi, shuning uchun yo‘nalishni bot ro‘yxatdagi kartalaringizga qarab o‘zi aniqlaydi: jo‘natuvchi karta sizniki — chiqim, qabul qiluvchi sizniki — kirim, ikkalasi ham sizniki — o‘z kartalar orasidagi o‘tkazma (yozmaslikni taklif qiladi va shu o‘tkazmaning avval saqlangan karta xabarini ham o‘chiradi). Kartalar ro‘yxatda bo‘lmasa, bot so‘raydi.
- **PDF chek** AI’siz o‘qiladi: fayldagi matn olinadi (birinchi 3 sahifa, 5 MB gacha) va oddiy xabar kabi qoidalardan o‘tadi. Matn qatlami bo‘lmagan (skaner qilingan) PDF uchun bot screenshot so‘raydi; ko‘p tranzaksiyali ko‘chirma (vypiska) qabul qilinmaydi.
- LLM’ga tranzaksiya matni, izoh va screenshot yuboriladi. Buni istamasangiz `LLM_PROVIDER=none` qoldiring: bot to‘liq ishlaydi, faqat erkin matnda ko‘proq savol beradi.

## Xavfsizlik

- Bot PIN, CVV, SMS kod, parol yoki to‘liq karta raqamini so‘ramaydi; to‘liq raqam yuborilsa rad etadi va xabarni chatdan o‘chirishga urinadi.
- Kartaning faqat oxirgi 4 ta raqami saqlanadi.
- `raw_text`, `user_note`, `ai_summary` bazada Fernet (AES) bilan shifrlangan. Summa, joy va oxirgi 4 raqam ochiq turadi, chunki hisobotlar shular bo‘yicha hisoblanadi; baza va uning zaxira nusxalarini ham himoyalang.
- Har bir so‘rov `user_id` bo‘yicha filtrlanadi: foydalanuvchi faqat o‘z ma’lumotini ko‘radi. Admin buyruqlari yo‘q.
- Token va kalitlar faqat `.env` da. Loglarda token, API kalit va karta raqami yashiriladi; xabar matni logga yozilmaydi.
- Redis ishlatilsa, tugallanmagan suhbat qoralamasi u yerda shifrlanmagan holda, ko‘pi bilan 24 soat turadi.
- `/settings` → «Ma’lumotlarimni o‘chirish» foydalanuvchining hamma yozuvlarini butunlay o‘chiradi.

## Loyiha tuzilmasi

```
app/
├── main.py                 ishga tushirish, migratsiya, polling
├── config.py               .env sozlamalari
├── database.py             SQLAlchemy async ulanish
├── models.py               users, cards, categories, transactions, merchant_rules
├── schemas.py              parser va LLM natijalari (Pydantic)
├── bot/
│   ├── dispatcher.py       middleware, routerlar, xatolarni ushlash
│   ├── middlewares.py      har bir yangilanish uchun sessiya va profil
│   ├── scheduler.py        kunlik, haftalik va oylik avtomatik hisobot
│   ├── states.py           suhbat holatlari
│   ├── keyboards.py        inline tugmalar
│   ├── render.py           xabar ko‘rinishlari
│   ├── texts.py            o‘zbekcha matnlar
│   └── handlers/           start, transactions, cards, reports, settings
├── services/
│   ├── parser.py           qoidalar + LLM zaxirasi
│   ├── llm.py              promptlar, Anthropic/OpenAI mijozlari
│   ├── notes.py            izoh tahlili (kishi soni, takrorlanish, tur taklifi)
│   ├── transfers.py        o‘z kartalar orasidagi o‘tkazmani tanish
│   ├── receipts.py         o‘tkazma cheklarini o‘qish (sarlavha–qiymat juftliklari)
│   ├── transaction_service.py
│   ├── report_service.py
│   ├── chart_service.py    hisobot rasmi (Pillow)
│   └── export_service.py
├── assets/fonts/           Inter shrifti (SIL OFL 1.1, litsenziyasi shu papkada)
└── utils/                  money, dates, validators, crypto, images, pdf, logging
migrations/                 Alembic
tests/                      pytest
```

## Testlar

```bash
pip install -r requirements-dev.txt
```

```bash
pytest
```

Testlar haqiqiy dispatcher’ni soxta Telegram sessiyasi bilan ishlatadi (`tests/bot_harness.py`), shuning uchun token ham, internet ham kerak emas. Lokal holatda ular tezlik uchun xotiradagi vaqtinchalik bazada ishlaydi; GitHub Actions’da PostgreSQL’da o‘tadi. O‘zingizda ham PostgreSQL’da tekshirish:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/moneytrack_test pytest
```

## Keyingi versiyalar uchun

Lokal (AI’siz) OCR, bir rasmdan bir nechta tranzaksiya, bank API integratsiyasi, real-time bank webhook, obuna to‘lovi, ko‘p foydalanuvchili analitika, Excel (`.xlsx`) eksport va boshqa interfeys tillari hozircha yo‘q.
