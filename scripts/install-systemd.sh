#!/bin/bash
set -e

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
PROJECT_DIR="$(dirname "$(dirname "$(realpath "$0")")")"
SYSTEMD_SOURCE_DIR="$PROJECT_DIR/systemd"

mkdir -p "$SYSTEMD_USER_DIR"

ln -sf "$SYSTEMD_SOURCE_DIR/on-torrent-finished.socket" "$SYSTEMD_USER_DIR/"
ln -sf "$SYSTEMD_SOURCE_DIR/on-torrent-finished@.service" "$SYSTEMD_USER_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now on-torrent-finished.socket

systemctl --user status on-torrent-finished.socket --no-pager
