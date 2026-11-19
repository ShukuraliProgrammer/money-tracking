"""Botning foydalanuvchiga ko‘rinadigan barcha matnlari (o‘zbek, lotin)."""

from __future__ import annotations

START = (
    "👋 Salom, {name}!\n\n"
    "📩 Karta xabarini (CardXabar, HUMO, bank SMS), screenshot’ini yoki PDF chekini shu botga forward qiling yoki matnini yuboring — men uni yozib boraman.\n\n"
    "📊 Hisobot: /report\n"
    "❓ Yordam: /help\n\n"
    "🔒 PIN, CVV, SMS kod yoki to‘liq karta raqamini hech qachon yubormang."
)

HELP = (
    "🤖 <b>MoneyTrack UZ</b>\n\n"
    "📩 Karta xabarini forward qiling, matnini, screenshot’ini yoki PDF chekini yuboring.\n\n"
    "<b>Tranzaksiyalar</b>\n"
    "➕ /add — qo‘lda qo‘shish\n"
    "🗑 /delete — oxirgisini o‘chirish\n"
    "❌ /cancel — bekor qilish\n\n"
    "<b>Hisobotlar</b>\n"
    "📊 /report — hisobot\n"
    "📈 /stat — statistika\n"
    "📄 /export — CSV fayl\n\n"
    "<b>Sozlash</b>\n"
    "💳 /cards — kartalar\n"
    "🆕 /addcard — karta qo‘shish\n"
    "🏷 /categories — turlar\n"
    "⚙️ /settings — sozlamalar\n\n"
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
CANCELLED = "❌ Bekor qilindi."
NOTHING_TO_CANCEL = "👌 Bekor qiladigan amal yo‘q."
TEMPORARY_ERROR = "⚠️ Vaqtincha xatolik, qayta urinib ko‘ring."
STALE_BUTTON = (
    "⌛ Bu tugma eskirgan.\n"
    "Xabarni qaytadan yuboring."
)
USE_BUTTONS = "👆 Iltimos, tugmalardan birini tanlang."
TEXT_ONLY = "📎 Matn, rasm (screenshot) yoki PDF chek yuboring — boshqa fayllarni o‘qiy olmayman."
PDF_FAILED = "📄 PDF faylni o‘qib bo‘lmadi.\n\nUning screenshot’ini yoki matnini yuboring."
PDF_NO_TEXT = "📄 Bu PDF ichida matn yo‘q — skaner qilingan bo‘lishi mumkin.\n\nUning screenshot’ini yuboring."
PDF_NO_TRANSACTION = "📄 Bu PDF’dan tranzaksiyani topa olmadim.\n\nBitta tranzaksiya chekini yuboring."
PDF_TOO_LONG = "📄 Bu PDF bitta chek emasga o‘xshaydi — matni juda uzun.\n\nBitta tranzaksiya chekini yuboring."
FILE_TOO_LARGE = "⚠️ Fayl juda katta (5 MB dan oshmasin)."
PHOTO_NEEDS_AI = (
    "🖼 Rasmni o‘qish uchun AI kaliti sozlanmagan.\n\n"
    "Hozircha xabarning matnini nusxalab yuboring."
)
PHOTO_FAILED = (
    "🖼 Rasmni o‘qib bo‘lmadi.\n\n"
    "Qayta urinib ko‘ring yoki xabarning matnini yuboring."
)
PHOTO_NO_TRANSACTION = (
    "🖼 Bu rasmda tranzaksiyani topa olmadim.\n\n"
    "Karta xabari yoki chek screenshot’ini yuboring."
)
PHOTO_FORMAT = (
    "🖼 Bu fayl formatini o‘qiy olmadim.\n\n"
    "Uni fayl emas, rasm sifatida yuboring."
)
PHOTO_TOO_LARGE = "🖼 Rasm juda katta (5 MB dan oshmasin)."
BUSY = "⏳ Avval joriy amalni yakunlang yoki /cancel bosing."
TOO_LONG = (
    "⚠️ Xabar juda uzun.\n"
    "Bitta tranzaksiya xabarini yuboring."
)

BTN_CANCEL = "❌ Bekor qilish"
BTN_EDIT = "✏️ Tahrirlash"
BTN_BACK = "⬅️ Orqaga"
BTN_YES = "✅ Ha"
BTN_NO = "❌ Yo‘q"
BTN_SKIP = "⏭ O‘tkazib yuborish"

# --- Tranzaksiya kiritish ---------------------------------------------------- #
ADD_PROMPT = (
    "🧾 Xarajat yoki daromadni yozing.\n\n"
    "Masalan:\n"
    "• Kamolonda 250 ming so‘m ovqatlandik\n"
    "• Maosh keldi 12 mln"
)
NOT_UNDERSTOOD = (
    "🤔 Tranzaksiyani tushunmadim.\n\n"
    "Masalan: Kamolonda 250 ming so‘m ovqatlandik"
)
SECRET_WARNING = (
    "🔒 Bu xabarda SMS kod, parol, PIN yoki CVV bo‘lishi mumkin — uni saqlamadim.\n\n"
    "Bunday kodlarni hech kimga yubormang."
)
PAN_NOTICE = (
    "🔒 To‘liq karta raqamini saqlamadim — faqat oxirgi 4 ta raqam.\n\n"
    "🗑 O‘sha xabarni chatdan o‘chirib tashlang."
)
HEAD_EXPENSE = "💸 <b>Chiqim</b>"
HEAD_INCOME = "💰 <b>Kirim</b>"
ASK_WHY = "📝 Nima uchun qilindi?"
FINISH_PENDING_FIRST = "⏳ Avval yuqoridagi tranzaksiyani yakunlang yoki «Bekor qilish»ni bosing."
NOTE_TOO_LONG = (
    "⚠️ Izoh juda uzun.\n"
    "500 belgidan qisqaroq yozing."
)
ASK_AMOUNT = (
    "💵 Summani aniqlay olmadim — uni yozing.\n\n"
    "Masalan: 250 000 yoki 250 ming"
)
EDIT_AMOUNT = (
    "💵 Yangi summani yozing.\n\n"
    "Masalan: 250 000 yoki 250 ming"
)
BAD_AMOUNT = (
    "⚠️ Summani tushunmadim.\n\n"
    "Masalan: 250 000 yoki 250 ming"
)
ASK_TYPE = "↕️ Bu kirimmi yoki chiqimmi?"
BTN_EXPENSE = "💸 Chiqim"
BTN_INCOME = "💰 Kirim"
ASK_DATE = (
    "🕓 Bu qachon bo‘lgan edi?\n\n"
    "Masalan: 19.11.2026 10:15"
)
BTN_NOW = "🕓 Hozir"
BTN_YESTERDAY = "⏪ Kecha"
BAD_DATE = (
    "⚠️ Sanani tushunmadim.\n\n"
    "Masalan: 19.11.2026 10:15, kecha 21:40 yoki 10:15"
)
FUTURE_DATE = (
    "⚠️ Sana kelajakda bo‘lishi mumkin emas.\n"
    "Qaytadan yozing."
)
DUPLICATE_WARNING = (
    "⚠️ Bunga o‘xshash tranzaksiya allaqachon saqlangan:\n\n"
    "{line}\n\n"
    "Baribir saqlaymi?"
)
BTN_SAVE_ANYWAY = "✅ Ha, baribir saqlash"
BTN_DROP = "❌ Yo‘q, bekor qilish"
BTN_OWN_TRANSFER = "🔁 O‘z kartamga o‘tkazma"
OWN_TRANSFER_SKIPPED = "🔁 O‘z kartalaringiz orasidagi o‘tkazma — hisobotga yozilmadi."
TRANSFER_SUSPECTED_PENDING = (
    "🔁 Bu ikki xabar o‘z kartalaringiz orasidagi o‘tkazmaga o‘xshaydi:\n\n"
    "{route}\n\n"
    "Ikkalasi ham hisobotga yozilmasinmi?"
)
TRANSFER_SUSPECTED_SAVED = (
    "🔁 Bu o‘z kartalaringiz orasidagi o‘tkazmaga o‘xshaydi:\n\n"
    "{route}\n\n"
    "Avval saqlangan qismi:\n"
    "{line}\n\n"
    "Ikkalasi ham hisobotga yozilmasinmi?"
)
TRANSFER_FEE = " (komissiya {fee})"
BTN_TRANSFER_YES = "✅ Ha, yozilmasin"
BTN_TRANSFER_NO = "➡️ Yo‘q, alohida tranzaksiya"
TRANSFER_DROPPED = "🔁 O‘tkazma hisobotga yozilmadi."
TRANSFER_DROPPED_WITH_SAVED = (
    "🔁 O‘tkazma hisobotga yozilmadi.\n"
    "Avval saqlangan qismi ham o‘chirildi."
)
EDIT_MENU = "✏️ Nimani tuzatamiz?"
BTN_EDIT_AMOUNT = "💵 Summa"
BTN_EDIT_MERCHANT = "📍 Joy"
BTN_EDIT_DATE = "🕓 Sana"
BTN_TO_INCOME = "🔁 Kirimga o‘zgartirish"
BTN_TO_EXPENSE = "🔁 Chiqimga o‘zgartirish"
EDIT_MERCHANT = "📍 Joy yoki kimdan kelganini yozing."
BAD_MERCHANT = "⚠️ Nom 1 dan 64 belgigacha bo‘lishi kerak."
ASK_CATEGORY = "🏷 Qaysi turga kiradi?"
BTN_NEW_CATEGORY = "➕ Yangi tur"
ASK_NEW_CATEGORY = (
    "🏷 Yangi tur nomini yozing — boshiga emoji qo‘yishingiz mumkin.\n\n"
    "Masalan: 🚕 Transport"
)
CATEGORY_NOT_FOUND = "⚠️ Tur topilmadi."
ASK_CARD_EXPENSE = "💳 Qaysi kartadan qilindi?"
ASK_CARD_INCOME = "💳 Qaysi kartaga tushdi?"
BTN_NEW_CARD = "➕ Yangi karta"
BTN_NO_CARD = "Kartasiz"
CARD_NOT_FOUND = "⚠️ Karta topilmadi."
ASK_NEW_CARD_NAME = (
    "💳 Yangi karta ****{last4} uchun nom yozing.\n\n"
    "Masalan: Asosiy Uzcard"
)
ASK_LAST4 = (
    "🔢 Kartaning oxirgi 4 ta raqamini yozing.\n\n"
    "🔒 To‘liq raqam kerak emas."
)
FULL_PAN_REFUSED = (
    "🔒 To‘liq karta raqamini yubormang — faqat oxirgi 4 ta raqam kerak.\n\n"
    "🗑 O‘sha xabarni chatdan o‘chirib tashlang."
)
BAD_LAST4 = (
    "⚠️ Faqat oxirgi 4 ta raqamni yozing.\n\n"
    "Masalan: 1234"
)
SAVED_HEAD = "✅ Saqlandi:"

# --- /delete ------------------------------------------------------------------ #
DELETE_CONFIRM = (
    "🗑 Oxirgi tranzaksiya:\n\n"
    "{line}\n\n"
    "O‘chiraymi?"
)
BTN_DELETE_YES = "🗑 Ha, o‘chirish"
DELETED = "🗑 O‘chirildi."
NO_TRANSACTIONS = "📭 Hali tranzaksiya yo‘q."
KEPT = "👌 O‘chirilmadi."

# --- Kartalar ------------------------------------------------------------------ #
CARDS_HEAD = "💳 <b>Kartalaringiz:</b>"
CARDS_EMPTY = "💳 Hali karta qo‘shilmagan."
INACTIVE = "nofaol"
BTN_ADD_CARD = "➕ Karta qo‘shish"
ASK_CARD_NAME = (
    "💳 Karta uchun nom yozing.\n\n"
    "Masalan: Asosiy Uzcard, Humo ish kartasi, Visa sayohat"
)
BAD_CARD_NAME = "⚠️ Karta nomi 1 dan 64 belgigacha bo‘lishi kerak."
ASK_NETWORK = "💳 Karta turi qaysi?"
BTN_OTHER_NETWORK = "Boshqa"
ASK_BANK = (
    "🏦 Bank nomini yozing yoki o‘tkazib yuboring.\n\n"
    "Masalan: Kapitalbank"
)
ASK_CURRENCY = "💱 Karta valyutasi qaysi?"
BAD_CURRENCY = (
    "⚠️ Valyuta kodini 3 ta harf bilan yozing.\n\n"
    "Masalan: UZS, USD, EUR"
)
CARD_ADDED = "✅ Karta qo‘shildi: {card}"
CARD_DELETE_CONFIRM = (
    "🗑 «{card}» kartasini o‘chiraymi?\n\n"
    "Tranzaksiyalari saqlanib qoladi."
)
CARD_DELETED = "🗑 Karta o‘chirildi."

# --- Turlar --------------------------------------------------------------------- #
CATEGORIES_HEAD = "🏷 <b>Turlar:</b>"
CATEGORY_ADDED = "✅ Tur qo‘shildi."
CATEGORY_DELETED = "🗑 Tur o‘chirildi."

# --- Hisobot ---------------------------------------------------------------------- #
ASK_PERIOD = "📅 Qaysi davr?"
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
REPORT_EMPTY = "📭 Bu davrda tranzaksiya yo‘q."
BTN_TRANSACTIONS = "🧾 Tranzaksiyalar ({count})"
BTN_CSV = "📄 CSV"
BTN_SUMMARY = "📊 Xulosa"
CSV_CAPTION = "📄 {label} — {count} ta tranzaksiya"
ASK_EXPORT_PERIOD = "📄 Qaysi davrni CSV faylga chiqaramiz?"
BTN_EXPORT_THIS_MONTH = "Bu oy"
BTN_EXPORT_PREV_MONTH = "O‘tgan oy"
WEEKLY_HEADING = "Haftalik hisobot"
DAILY_HEADING = "Bugungi hisobot"
DAILY_MORE = "… va yana {count} ta tranzaksiya — to‘liq ro‘yxat pastdagi tugmada."
MONTHLY_HEADING = "Oylik hisobot"
REPORT_HEADING = "Hisobot"
REPORT_PHOTO_CAPTION = "🗓 {heading} · {period}"
BTN_PICTURE = "🖼 Rasm"
PICTURE_FAILED = (
    "⚠️ Rasmni tayyorlab bo‘lmadi.\n"
    "Matnli hisobotdan foydalaning."
)

# --- Sozlamalar --------------------------------------------------------------------- #
SETTINGS = (
    "⚙️ <b>Sozlamalar</b>\n\n"
    "🕓 Vaqt zonasi: {timezone}\n"
    "💱 Valyuta: {currency}\n\n"
    "🔔 <b>Avtomatik hisobotlar</b>\n"
    "🌙 Kunlik — har kuni 21:00\n"
    "📆 Haftalik — dushanba 09:00\n"
    "🗓 Oylik — har oyning 1-kuni 09:00"
)
BTN_TIMEZONE = "🕓 Vaqt zonasi"
BTN_CURRENCY = "💱 Valyuta"
BTN_NOTIFICATIONS = "🗓 Oylik {mark}"
BTN_WEEKLY = "📆 Haftalik {mark}"
BTN_DAILY = "🌙 Kunlik {mark}"
MARK_ON = "✅"
MARK_OFF = "❌"
BTN_WIPE = "🗑 Ma’lumotlarimni o‘chirish"
ASK_TIMEZONE = (
    "🕓 Vaqt zonasini tanlang yoki nomini yozing.\n\n"
    "Masalan: Asia/Tashkent"
)
TIMEZONE_NOT_FOUND = (
    "⚠️ Bunday vaqt zonasi topilmadi.\n\n"
    "Masalan: Asia/Tashkent, Europe/Moscow"
)
ASK_SETTINGS_CURRENCY = "💱 Asosiy valyutani tanlang."
WIPE_CONFIRM = (
    "⚠️ Barcha ma’lumotlaringiz — kartalar, turlar va tranzaksiyalar — butunlay o‘chiriladi.\n"
    "Buni qaytarib bo‘lmaydi.\n\n"
    "Davom etaymi?"
)
BTN_WIPE_YES = "🗑 Ha, hammasini o‘chirish"
WIPED = (
    "🗑 Barcha ma’lumotlaringiz o‘chirildi.\n\n"
    "Qaytadan boshlash uchun /start bosing."
)
