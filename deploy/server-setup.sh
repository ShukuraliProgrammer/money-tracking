#!/usr/bin/env bash
# MoneyTrack UZ — serverni bir marta tayyorlash (Ubuntu yoki Debian).
#
# Nima qiladi:
#   1. Docker o'rnatilmagan bo'lsa, o'rnatadi (o'rnatilgan bo'lsa, tegmaydi).
#   2. Deploy uchun alohida foydalanuvchi yaratadi va unga SSH ochiq kalitingizni qo'shadi.
#   3. Bot papkasini va .env faylini yaratadi (shifrlash kaliti bilan).
#
# Ishga tushirish (root sifatida), argument — ochiq kalit (.pub fayl mazmuni):
#   sudo bash server-setup.sh "ssh-ed25519 AAAA... moneytrack-deploy"
#
# Qayta ishga tushirish xavfsiz: bor narsalarni buzmaydi, .env ni qayta yozmaydi.

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/moneytrack}"
PUBLIC_KEY="${1:-}"

die() {
  echo "Xato: $*" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || die "skriptni root sifatida ishga tushiring (sudo bash server-setup.sh ...)."
case "$PUBLIC_KEY" in
  "ssh-ed25519 "* | "ssh-rsa "* | "ecdsa-sha2-"*) ;;
  "") die "ochiq kalitni argument sifatida bering: sudo bash server-setup.sh \"ssh-ed25519 AAAA...\"" ;;
  *) die "bu SSH ochiq kalitiga o'xshamaydi. Maxfiy kalitni emas, .pub fayl mazmunini bering." ;;
esac
command -v apt-get > /dev/null || die "bu skript faqat Ubuntu/Debian uchun (apt-get topilmadi)."

echo "==> Kerakli paketlar"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl rsync openssl > /dev/null

echo "==> Docker"
if command -v docker > /dev/null; then
  echo "    Docker allaqachon o'rnatilgan: $(docker --version)"
else
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh > /dev/null
  rm -f /tmp/get-docker.sh
  echo "    O'rnatildi: $(docker --version)"
fi
if ! docker compose version > /dev/null 2>&1; then
  apt-get install -y -qq docker-compose-plugin > /dev/null || die "docker compose plaginini o'rnatib bo'lmadi."
fi
systemctl enable --now docker > /dev/null 2>&1 || true

echo "==> Foydalanuvchi: $DEPLOY_USER"
if ! id "$DEPLOY_USER" > /dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi
# docker guruhi a'zosi konteynerlarni boshqara oladi (bu serverda root huquqiga teng), shuning uchun
# bu foydalanuvchiga faqat deploy kaliti bilan kiriladi, paroli yo'q.
usermod -aG docker "$DEPLOY_USER"
HOME_DIR="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$HOME_DIR/.ssh"
touch "$HOME_DIR/.ssh/authorized_keys"
grep -qxF "$PUBLIC_KEY" "$HOME_DIR/.ssh/authorized_keys" || echo "$PUBLIC_KEY" >> "$HOME_DIR/.ssh/authorized_keys"
chmod 600 "$HOME_DIR/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "$HOME_DIR/.ssh/authorized_keys"

echo "==> Papka: $DEPLOY_PATH"
install -d -m 750 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$DEPLOY_PATH"
ENV_FILE="$DEPLOY_PATH/.env"
if [ -f "$ENV_FILE" ]; then
  echo "    .env allaqachon bor, o'zgartirilmadi."
else
  # Fernet kaliti: 32 tasodifiy bayt, URL-xavfsiz base64.
  ENCRYPTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_')"
  cat > "$ENV_FILE" <<ENV
# MoneyTrack UZ sozlamalari. To'liq ro'yxat: .env.example
BOT_TOKEN=
ENCRYPTION_KEY=$ENCRYPTION_KEY
DATABASE_URL=sqlite+aiosqlite:///./data/moneytrack.db
LLM_PROVIDER=none
ENV
  chown "$DEPLOY_USER:$DEPLOY_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "    .env yaratildi (shifrlash kaliti bilan)."
fi

HOST_KEY="$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub 2> /dev/null || true)"

cat <<DONE

Tayyor. Endi:

1. Bot tokenini yozing:
     nano $ENV_FILE        (BOT_TOKEN= qatoriga @BotFather bergan tokenni qo'ying)
   Avvalgi bazani ko'chirayotgan bo'lsangiz, ENCRYPTION_KEY ni eski qiymatiga almashtiring.

2. GitHub'da (Settings → Secrets and variables → Actions) sirlarni kiriting:
     DEPLOY_HOST         serverning IP manzili
     DEPLOY_USER         $DEPLOY_USER
     DEPLOY_SSH_KEY      maxfiy kalit faylining to'liq mazmuni
     DEPLOY_PATH         $DEPLOY_PATH   (standart /opt/moneytrack bo'lsa, shart emas)
     DEPLOY_KNOWN_HOSTS  <server IP> $HOST_KEY

3. GitHub → Actions → "CI/CD" → "Run workflow".
DONE
