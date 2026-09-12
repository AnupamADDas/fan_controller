#!/bin/bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
    echo 'Run this installer with sudo.' >&2
    exit 1
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 "$source_dir/asus-fan-controller.py" --check
systemctl show-environment >/dev/null
systemd-analyze verify "$source_dir/asus-fan-controller.service"
install -o root -g root -m 0755 "$source_dir/asus-fan-controller.py" /usr/local/sbin/asus-fan-controller.py
install -o root -g root -m 0644 "$source_dir/asus-fan-controller.service" /etc/systemd/system/asus-fan-controller.service
systemctl daemon-reload
systemctl enable asus-fan-controller.service
systemctl restart asus-fan-controller.service
sleep 3
if ! systemctl is-active --quiet asus-fan-controller.service; then
    systemctl disable --now asus-fan-controller.service || true
    python3 /usr/local/sbin/asus-fan-controller.py --restore-auto
    journalctl -u asus-fan-controller.service -n 20 --no-pager
    exit 1
fi
systemctl status asus-fan-controller.service --no-pager
