#!/usr/bin/env bash
# One-shot (and re-runnable) installer for an Ubuntu 22.04 / 24.04 EC2 instance.
# Run it from inside the unzipped project folder:   bash deploy/ec2/setup.sh
set -euo pipefail

APP_DIR=/opt/caredesk
APP_USER="${SUDO_USER:-$USER}"

if [ ! -f .env ]; then
  echo "No .env file found. Run:  cp .env.example .env   then edit it (database, S3, SECRET_KEY)."
  exit 1
fi

echo "==> Installing system packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip nginx rsync

echo "==> Copying the project to $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo rsync -a --delete --exclude venv --exclude .git --exclude db.sqlite3 --exclude media --exclude staticfiles ./ "$APP_DIR"/
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

cd "$APP_DIR"
echo "==> Creating the virtual environment"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

echo "==> Checking the database (RDS) and file storage (S3) are reachable"
./venv/bin/python manage.py check_aws

echo "==> Running migrations, collecting static files, creating first admin"
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py bootstrap

echo "==> Installing the systemd service and Nginx site"
sed "s/__USER__/$APP_USER/" deploy/ec2/gunicorn.service | sudo tee /etc/systemd/system/caredesk.service >/dev/null
sudo cp deploy/ec2/nginx.conf /etc/nginx/sites-available/caredesk
sudo ln -sf /etc/nginx/sites-available/caredesk /etc/nginx/sites-enabled/caredesk
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable --now caredesk
sudo systemctl restart caredesk
sudo nginx -t
sudo systemctl restart nginx

echo
echo "Done. Open http://<this-instance-public-ip>/ in your browser."
echo "Logs:  sudo journalctl -u caredesk -f"
