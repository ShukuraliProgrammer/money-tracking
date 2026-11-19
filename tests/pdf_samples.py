"""Testlar uchun kichik PDF fayllar yasash (ma'lumotlar to'qima)."""

import io

from PIL import Image

RECEIPT_LINES = [
    "Receipt",
    "Sender 986017******9298",
    "Sender name TESTOV TEST",
    "Receiver 860012******4321",
    "Receiver name ALIYEV VALI",
    "Transaction ID 4701fa17-7f4f-4530-8558",
    "Transaction date 19.11.2026 14:00:22",
    "Amount 150 000.00 UZS",
    "Commission 0.00 UZS",
    "Status Success",
]


def make_pdf(lines: list[str]) -> bytes:
    """Matn qatlamli bir sahifali PDF (faqat lotin harflari)."""

    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content = ("BT /F1 12 Tf 50 780 Td 16 TL " + " ".join(f"({escape(line)}) Tj T*" for line in lines) + " ET").encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def make_scanned_pdf() -> bytes:
    """Faqat rasmdan iborat PDF (matn qatlami yo'q), skaner qilingan chek kabi."""
    buffer = io.BytesIO()
    Image.new("RGB", (60, 80), (255, 255, 255)).save(buffer, format="PDF")
    return buffer.getvalue()

# Uzum Bank o'tkazma chekining haqiqiy tuzilishi: avval barcha sarlavhalar, keyin barcha qiymatlar
# (foydalanuvchi yuborgan chek asosida; karta raqamlari, ismlar va ID to'qima).
UZUM_LABELS = [
    "Sender", "Sender name", "Receiver", "Receiver name", "Transaction ID", "Transaction date",
    "Received date", "Receiver fee", "Receiver amount", "Sender fee", "Sender amount",
]  # fmt: skip


def uzum_receipt_lines(sender_amount="1,000.00 UZS", receiver_amount="1,000.00 UZS", sender_fee="0.00 UZS") -> list[str]:
    values = [
        "441122******3344", "TESTOV TEST", "986017******5566", "TESTOV T",
        "0a1b2c3d-71af-4568-8836-2db8a43a760a", "19.11.2026 10:28:23", "19.11.2026 10:28:24",
        "0.00 UZS", receiver_amount, sender_fee, sender_amount,
    ]  # fmt: skip
    return [*UZUM_LABELS, *values]
