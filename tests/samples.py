"""Testlarda ishlatiladigan namuna xabarlar (karta raqamlari to'qima)."""

HUMO_EXPENSE = """💸 Oplata
➖ 54.000,00 UZS
📍 YANDEX GO
💳 HUMOCARD *1234
🕓 12:01 19.11.2026
💰 1.234.567,00 UZS"""

HUMO_INCOME = """🎉 Popolnenie
➕ 1.000.000,00 UZS
📍 P2P HUMO UZCARD
💳 HUMOCARD *6157
🕓 17:26 03.06.2026
💰 1.526.871,58 UZS"""

CARDXABAR_EXPENSE = """🔴 Pokupka
➖ 250 000.00 UZS
💳 ***1234
📍 KAMOLON OSH MARKAZI
🕓 19.11.26 10:15
💵 1 034 567.89 UZS"""

BANK_SMS_USD = "Pokupka: 12.50 USD. Karta *4321. Merchant: AMAZON.COM. 19.11.2026 10:15. Dostupno: 487.50 USD"

BANK_SMS_UZ = "Karta *4321: xarid 150 000 so'm, KORZINKA. 19.11.2026 10:15. Qoldiq: 2 345 000 so'm"

BANK_SMS_RU = "Покупка 150 000 сум. Карта *1234. 19.11.2026 10:15. Доступно: 1 000 000 сум"

MANUAL_FOOD = "Kamolonda 250 ming so'm ovqatlandik"

# O'z kartalar orasidagi o'tkazma: bir kartadan chiqim, boshqasiga shu summada kirim.
TRANSFER_OUT = """💸 Perevod
➖ 1.000.000,00 UZS
📍 P2P HUMO UZCARD
💳 HUMOCARD *1234
🕓 12:01 19.11.2026
💰 234.567,00 UZS"""

TRANSFER_IN = """🎉 Popolnenie
➕ 1.000.000,00 UZS
📍 P2P HUMO UZCARD
💳 HUMOCARD *5678
🕓 12:02 19.11.2026
💰 1.526.871,58 UZS"""

# Haqiqiy botlardagi format (foydalanuvchi yuborgan screenshot'lar asosida; raqamlar o'zgartirilgan).
REAL_CARDXABAR_ECOM = """🔴 E-Com oplata
➖ 32 520.00 UZS
💳 ***4417
📍 PAYME OPLATA, UZ
🕓 18.11.26 19:19
💵 139 076.28 UZS"""

REAL_HUMO_TOPUP = """🎉 To'ldirish
➕ 1.000,00 UZS
📍 UB Visa to Humo P2P>
💳 HUMOCARD *7731
🕓 10:28 19.11.2026
💰 1.092,00 UZS"""
