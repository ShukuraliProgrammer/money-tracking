#!/usr/bin/env bash
# MoneyTrack UZ — serverni tayyorlash (Ubuntu yoki Debian). Repo'ni clone qilgandan keyin,
# uning ichidan ishga tushiriladi:
#
#   git clone https://github.com/ShukuraliProgrammer/money-tracking.git
#   cd money-tracking
#   sudo bash deploy/server-setup.sh
#
# Nima qiladi:
#   1. Docker o'rnatilmagan bo'lsa, o'rnatadi.
#   2. Shu papkada .env faylini yaratadi (shifrlash kaliti va PostgreSQL paroli bilan).
#   3. Argument sifatida SSH ochiq kaliti berilsa, uni sizning foydalanuvchingizga qo'shadi —
#      GitHub Actions serverni shu kalit bilan yangilaydi:
#        sudo bash deploy/server-setup.sh "ssh-ed25519 AAAA... moneytrack-deploy"
#
# Qayta ishga tushirish xavfsiz: bor narsalarni buzmaydi, .env ni qayta yozmaydi.

set -euo pipefail

PUBLIC_KEY="${1:-}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_AS="${SUDO_USER:-root}"

die() {
  echo "Xato: $*" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || die "skriptni sudo bilan ishga tushiring: sudo bash deploy/server-setup.sh"
case "$PUBLIC_KEY" in
  "" | "ssh-ed25519 "* | "ssh-rsa "* | "ecdsa-sha2-"*) ;;
  *) die "bu SSH ochiq kalitiga o'xshamaydi. Maxfiy kalitni emas, .pub fayl mazmunini bering." ;;
esac
command -v apt-get > /dev/null || die "bu skript faqat Ubuntu/Debian uchun (apt-get topilmadi)."

echo "==> Docker"
if command -v docker > /dev/null; then
  echo "    Allaqachon o'rnatilgan: $(docker --version)"
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl > /dev/null
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh > /dev/null
  rm -f /tmp/get-docker.sh
  echo "    O'rnatildi: $(docker --version)"
fi
if [ "$RUN_AS" != root ]; then
  # docker guruhi a'zosi konteynerlarni sudo'siz boshqara oladi (bu serverda root huquqiga teng).
  usermod -aG docker "$RUN_AS"
fi

echo "==> .env ($REPO_DIR)"
ENV_FILE="$REPO_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  echo "    Allaqachon bor, o'zgartirilmadi."
else
  # Fernet kaliti: 32 tasodifiy bayt, URL-xavfsiz base64.
  cat > "$ENV_FILE" <<ENV
# MoneyTrack UZ sozlamalari. To'liq ro'yxat: .env.example
BOT_TOKEN=
ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
POSTGRES_PASSWORD=$(openssl rand -hex 24)
LLM_PROVIDER=none
ENV
  chown "$RUN_AS:" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "    Yaratildi (shifrlash kaliti va PostgreSQL paroli bilan)."
fi

if [ -n "$PUBLIC_KEY" ]; then
  echo "==> SSH kaliti ($RUN_AS)"
  HOME_DIR="$(getent passwd "$RUN_AS" | cut -d: -f6)"
  install -d -m 700 -o "$RUN_AS" "$HOME_DIR/.ssh"
  touch "$HOME_DIR/.ssh/authorized_keys"
  grep -qxF "$PUBLIC_KEY" "$HOME_DIR/.ssh/authorized_keys" || echo "$PUBLIC_KEY" >> "$HOME_DIR/.ssh/authorized_keys"
  chown "$RUN_AS:" "$HOME_DIR/.ssh/authorized_keys"
  chmod 600 "$HOME_DIR/.ssh/authorized_keys"
fi

cat <<DONE

Tayyor. Endi:

1. Bot tokenini yozing:   nano $ENV_FILE
2. Botni ishga tushiring: cd $REPO_DIR && docker compose up -d --build
   (docker guruhiga hozir qo'shilgan bo'lsangiz, avval serverga qayta kiring yoki sudo ishlating)
DONE
