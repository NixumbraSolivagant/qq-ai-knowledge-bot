#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
service_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service_name="qq-knowledge-bot.service"

if [[ $EUID -eq 0 ]]; then
  echo "请使用普通用户运行此脚本，不要使用 sudo。"
  exit 1
fi

if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  echo "未找到虚拟环境：$project_dir/.venv/bin/python"
  echo "请先执行：python3 -m venv .venv && .venv/bin/pip install -e ."
  exit 1
fi

mkdir -p "$service_dir"
cat > "$service_dir/$service_name" <<UNIT
[Unit]
Description=QQ AI Knowledge Bot (NoneBot)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$project_dir
EnvironmentFile=$project_dir/.env
Environment=NO_PROXY=127.0.0.1,localhost,::1
Environment=no_proxy=127.0.0.1,localhost,::1
ExecStart=$project_dir/.venv/bin/python $project_dir/bot.py
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=20

[Install]
WantedBy=default.target
UNIT

chmod 600 "$project_dir/.env"
systemctl --user daemon-reload
systemctl --user enable --now "$service_name"
loginctl enable-linger "$USER" >/dev/null 2>&1 || true

echo "已启用 $service_name"
echo "查看日志：journalctl --user -u $service_name -f"
echo "NapCat 请按其官方文档单独配置为开机启动。"
