"""Botning foydalanuvchiga ko‘rinadigan barcha matnlari (o‘zbek, lotin)."""

from __future__ import annotations

START = (
    "👋 Salom, {name}! Men <b>MoneyTrack UZ</b> — kartalaringizdagi kirim va chiqimlarni kuzatishga yordam beraman.\n\n"
    "🧾 Xarajat yoki daromad xabarini shu botga forward qiling yoki matnini yuboring. "
    "CardXabarBot yoki HUMOcardbot xabari, bank SMS’i yoki oddiy matn "
    "(«Kamolonda 250 ming so‘m ovqatlandik») — hammasi bo‘ladi.\n\n"
    "Har bir tranzaksiya uchun uchta savol beraman:\n"
    "1. Nima uchun qilindi?\n"
    "2. Qaysi turga kiradi?\n"
    "3. Qaysi kartadan qilindi?\n\n"
    "📊 Oy oxirida /report orqali hamma kartalaringiz bo‘yicha hisobot olasiz.\n\n"
    "🔒 Men hech qachon PIN, CVV, SMS kod yoki to‘liq karta raqamini so‘ramayman. "
    "Kartaning faqat oxirgi 4 ta raqami saqlanadi.\n\n"
    "Boshlash uchun /addcard bilan kartangizni qo‘shing yoki darhol xabar yuboring. Yordam: /help"
)

HELP = (
    "<b>MoneyTrack UZ — yordam</b>\n\n"
    "🧾 Tranzaksiya qo‘shish: karta xabarini forward qiling yoki matnini yuboring.\n\n"
    "/add — qo‘lda tranzaksiya qo‘shish\n"
    "/cards — kartalar ro‘yxati\n"
    "/addcard — yangi karta qo‘shish\n"
    "/report — hisobot (davr, karta va tur bo‘yicha)\n"
    "/stat — oxirgi 30 kun statistikasi\n"
    "/categories — turlar (kategoriyalar)\n"
    "/export — CSV faylga eksport\n"
    "/delete — oxirgi tranzaksiyani o‘chirish\n"
    "/settings — vaqt zonasi, valyuta, bildirishnoma, ma’lumotlarni o‘chirish\n"
    "/cancel — joriy amalni bekor qilish\n\n"
    "🔒 PIN, CVV, SMS kod yoki to‘liq karta raqamini hech qachon yubormang."
)

BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Botni tanishtirish"),
    ("add", "Qo‘lda tranzaksiya qo‘shish"),
    ("cards", "Kartalar ro‘yxati"),
    ("addcard", "Yangi karta qo‘shish"),
    ("report", "Hisobot"),
    ("stat", "Statistika"),
    ("categories", "Turlar"),
    ("export", "CSV eksport"),
    ("delete", "Oxirgi tranzaksiyani o‘chirish"),
    ("settings", "Sozlamalar"),
    ("help", "Yordam"),
)

# --- Umumiy ---------------------------------------------------------------- #
CANCELLED = "Bekor qilindi."
NOTHING_TO_CANCEL = "Bekor qiladigan amal yo‘q."
TEMPORARY_ERROR = "⚠️ Vaqtincha xatolik, qayta urinib ko‘ring."
STALE_BUTTON = "Bu tugma eskirgan. Xabarni qaytadan yuboring."
USE_BUTTONS = "Iltimos, tugmalardan birini tanlang 👆"
TEXT_ONLY = "Hozircha faqat matnli xabarlarni tushunaman. Tranzaksiya matnini yuboring."
PHOTO_NOT_SUPPORTED = (
    "🖼 Screenshot’ni o‘qish keyingi versiyada qo‘shiladi. Hozircha xabarning matnini nusxalab yuboring."
)
TOO_LONG = "Xabar juda uzun. Bitta tranzaksiya haqidagi xabarni yuboring."

BTN_CANCEL = "❌ Bekor qilish"
BTN_EDIT = "✏️ Tahrirlash"
BTN_BACK = "⬅️ Orqaga"
BTN_YES = "Ha"
BTN_NO = "Yo‘q"
BTN_SKIP = "O‘tkazib yuborish"

# --- Tranzaksiya kiritish ---------------------------------------------------- #
ADD_PROMPT = (
    "🧾 Xarajat yoki daromadni yozing.\n"
    "Masalan: «Kamolonda 250 ming so‘m ovqatlandik» yoki «Maosh keldi 12 mln»."
)
NOT_UNDERSTOOD = (
    "Bu xabardan tranzaksiyani tushunmadim 🙂\n"
    "Karta xabarini forward qiling yoki summa bilan yozing, masalan: «Kamolonda 250 ming so‘m ovqatlandik»."
)
SECRET_WARNING = (
    "🔒 Bu xabarda SMS kod, parol, PIN yoki CVV bo‘lishi mumkin, shuning uchun uni saqlamadim.\n"
    "Bunday kodlarni hech kimga, jumladan botlarga ham yubormang. "
    "Menga faqat to‘lov yoki tushum haqidagi xabar kerak."
)
PAN_NOTICE = (
    "ℹ️ Xabaringizda to‘liq karta raqami bor edi. Men faqat oxirgi 4 ta raqamni saqladim. "
    "Xavfsizlik uchun o‘sha xabarni chatdan o‘chirib tashlashni tavsiya qilaman."
)
HEAD_EXPENSE = "💸 <b>Chiqim aniqlandi:</b>"
HEAD_INCOME = "💰 <b>Kirim aniqlandi:</b>"
ASK_WHY = "Nima uchun qilindi?"
FINISH_PENDING_FIRST = (
    "Avval yuqoridagi tranzaksiyani yakunlaylik: u nima uchun qilingan edi?\n"
    "Kerak bo‘lmasa, «Bekor qilish» tugmasini bosing, keyin yangi xabarni qayta yuboring."
)
NOTE_TOO_LONG = "Izoh juda uzun. 500 belgidan qisqaroq yozing."
ASK_AMOUNT = "Summani aniqlay olmadim. Summani yozing, masalan: 250 000 yoki 250 ming."
EDIT_AMOUNT = "Yangi summani yozing, masalan: 250 000 yoki 250 ming."
BAD_AMOUNT = "Summani tushunmadim. Faqat summani yozing, masalan: 250 000 yoki 250 ming."
ASK_TYPE = "Bu kirimmi yoki chiqimmi?"
BTN_EXPENSE = "💸 Chiqim"
BTN_INCOME = "💰 Kirim"
ASK_DATE = "Bu qachon bo‘lgan edi?\nTugmani bosing yoki sanani yozing, masalan: 19.11.2026 10:15."
BTN_NOW = "🕓 Hozir"
BTN_YESTERDAY = "Kecha"
BAD_DATE = "Sanani tushunmadim. Masalan: 19.11.2026 10:15, «kecha 21:40» yoki «10:15»."
FUTURE_DATE = "Sana kelajakda bo‘lishi mumkin emas. Qaytadan yozing."
DUPLICATE_WARNING = "⚠️ Bunga o‘xshash tranzaksiya allaqachon saqlangan:\n{line}\n\nBaribir saqlaymi?"
BTN_SAVE_ANYWAY = "Ha, baribir saqlash"
BTN_DROP = "Yo‘q, bekor qilish"
EDIT_MENU = "Nimani tuzatamiz?"
BTN_EDIT_AMOUNT = "Summa"
BTN_EDIT_MERCHANT = "Joy"
BTN_EDIT_DATE = "Sana"
BTN_TO_INCOME = "🔁 Kirimga o‘zgartirish"
BTN_TO_EXPENSE = "🔁 Chiqimga o‘zgartirish"
EDIT_MERCHANT = "Joy yoki kimdan kelganini yozing."
BAD_MERCHANT = "Nom 1 dan 64 belgigacha bo‘lishi kerak."
ASK_CATEGORY = "Qaysi turga kiradi?"
SUGGESTED_HINT = "⭐ — taklif qilingan tur."
BTN_NEW_CATEGORY = "➕ Yangi tur"
ASK_NEW_CATEGORY = "Yangi tur nomini yozing. Boshiga emoji qo‘yishingiz mumkin, masalan: 🚕 Transport."
CATEGORY_NOT_FOUND = "Tur topilmadi."
ASK_CARD_EXPENSE = "Qaysi kartadan qilindi?"
ASK_CARD_INCOME = "Qaysi kartaga tushdi?"
NO_CARDS_HINT = "Hali karta qo‘shilmagan — «Yangi karta» tugmasi bilan qo‘shing."
BTN_NEW_CARD = "➕ Yangi karta"
BTN_NO_CARD = "Kartasiz"
CARD_NOT_FOUND = "Karta topilmadi."
ASK_NEW_CARD_NAME = "Yangi karta ****{last4} uchun nom yozing, masalan: Asosiy Uzcard."
ASK_LAST4 = "Kartaning oxirgi 4 ta raqamini yozing.\n🔒 To‘liq raqam kerak emas."
FULL_PAN_REFUSED = (
    "🔒 To‘liq karta raqamini yubormang. Menga faqat oxirgi 4 ta raqam kerak.\n"
    "Xavfsizlik uchun o‘sha xabarni chatdan o‘chirib tashlang."
)
BAD_LAST4 = "Faqat oxirgi 4 ta raqamni yozing, masalan: 1234."
SAVED_HEAD = "✅ <b>Saqlandi:</b>"

# --- /delete ------------------------------------------------------------------ #
DELETE_CONFIRM = "Oxirgi tranzaksiya:\n{line}\n\nO‘chiraymi?"
BTN_DELETE_YES = "🗑 Ha, o‘chirish"
DELETED = "🗑 O‘chirildi."
NO_TRANSACTIONS = "Hali tranzaksiya yo‘q."
KEPT = "O‘chirilmadi."

# --- Kartalar ------------------------------------------------------------------ #
CARDS_HEAD = "💳 <b>Kartalaringiz:</b>"
CARDS_EMPTY = "💳 Hali karta qo‘shilmagan."
CARDS_HINT = "⏸ — vaqtincha o‘chirish, ▶️ — qayta yoqish, 🗑 — o‘chirish."
INACTIVE = "nofaol"
BTN_ADD_CARD = "➕ Karta qo‘shish"
ASK_CARD_NAME = "💳 Karta uchun nom yozing, masalan: Asosiy Uzcard, Humo ish kartasi, Visa sayohat."
BAD_CARD_NAME = "Karta nomi 1 dan 64 belgigacha bo‘lishi kerak."
ASK_NETWORK = "Karta turi qaysi?"
BTN_OTHER_NETWORK = "Boshqa"
ASK_BANK = "Bank nomini yozing (masalan: Kapitalbank) yoki o‘tkazib yuboring."
ASK_CURRENCY = "Karta valyutasi qaysi?"
BAD_CURRENCY = "Valyuta kodini 3 ta harf bilan yozing, masalan: UZS, USD, EUR."
CARD_ADDED = "✅ Karta qo‘shildi: {card}"
CARD_DELETE_CONFIRM = (
    "«{card}» kartasini o‘chiraymi?\nUning tranzaksiyalari saqlanib qoladi, lekin kartasiz bo‘lib ko‘rinadi."
)
CARD_DELETED = "🗑 Karta o‘chirildi."

# --- Turlar --------------------------------------------------------------------- #
CATEGORIES_HEAD = "🏷 <b>Turlar:</b>"
CATEGORIES_HINT = "🗑 tugmasi bilan o‘zingiz qo‘shgan turni o‘chirishingiz mumkin."
CATEGORY_ADDED = "✅ Tur qo‘shildi."
CATEGORY_DELETED = "🗑 Tur o‘chirildi."

# --- Hisobot ---------------------------------------------------------------------- #
ASK_PERIOD = "📊 Qaysi davr uchun hisobot kerak?"
ASK_REPORT_CARD = "💳 Qaysi karta bo‘yicha?"
ASK_REPORT_CATEGORY = "🏷 Qaysi tur bo‘yicha?"
BTN_TODAY = "Bugun"
BTN_WEEK = "Bu hafta"
BTN_THIS_MONTH = "Bu oy ({label})"
BTN_PREV_MONTH = "O‘tgan oy ({label})"
BTN_LAST_30 = "Oxirgi 30 kun"
BTN_ALL_TIME = "Hamma vaqt"
ALL_CARDS = "Hamma kartalar"
ALL_CATEGORIES = "Hamma turlar"
UNKNOWN_CARD = "noma’lum karta"
UNKNOWN_CATEGORY = "noma’lum tur"
REPORT_EMPTY = "Bu davrda tranzaksiya yo‘q."
BTN_TRANSACTIONS = "🧾 Tranzaksiyalar ({count})"
BTN_CSV = "📄 CSV"
BTN_FILTER = "🔎 Filtr"
BTN_PERIOD = "📅 Davr"
BTN_SUMMARY = "📊 Xulosa"
CSV_CAPTION = "📄 {label} — {count} ta tranzaksiya"
ASK_EXPORT_PERIOD = "📄 Qaysi davrni CSV faylga chiqaramiz?"
BTN_EXPORT_THIS_MONTH = "Bu oy"
BTN_EXPORT_PREV_MONTH = "O‘tgan oy"
MONTHLY_REPORT_INTRO = "🗓 O‘tgan oy yakunlandi. Mana hisobotingiz:\n\n"

# --- Sozlamalar --------------------------------------------------------------------- #
SETTINGS = (
    "⚙️ <b>Sozlamalar</b>\n\n"
    "Til: O‘zbek (lotin)\n"
    "Vaqt zonasi: {timezone}\n"
    "Asosiy valyuta: {currency}\n"
    "Oylik hisobot: {notifications}"
)
ON = "yoqilgan"
OFF = "o‘chirilgan"
BTN_TIMEZONE = "🕓 Vaqt zonasi"
BTN_CURRENCY = "💱 Valyuta"
BTN_NOTIFICATIONS = "🔔 Oylik hisobot: {state}"
BTN_WIPE = "🗑 Ma’lumotlarimni o‘chirish"
ASK_TIMEZONE = "Vaqt zonasini tanlang yoki nomini yozing, masalan: Asia/Tashkent."
TIMEZONE_NOT_FOUND = "Bunday vaqt zonasi topilmadi. Masalan: Asia/Tashkent, Europe/Moscow."
ASK_SETTINGS_CURRENCY = "Asosiy valyutani tanlang."
WIPE_CONFIRM = (
    "⚠️ Barcha ma’lumotlaringiz — kartalar, turlar va tranzaksiyalar — butunlay o‘chiriladi. "
    "Buni qaytarib bo‘lmaydi.\n\nDavom etaymi?"
)
BTN_WIPE_YES = "Ha, hammasini o‘chirish"
WIPED = "🗑 Barcha ma’lumotlaringiz o‘chirildi. Qaytadan boshlash uchun /start bosing."
