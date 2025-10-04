#!/bin/bash
set -e

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

systemctl --user stop on-torrent-finished.socket 2>/dev/null || true
systemctl --user disable on-torrent-finished.socket 2>/dev/null || true

rm -f "$SYSTEMD_USER_DIR/on-torrent-finished.socket"
rm -f "$SYSTEMD_USER_DIR/on-torrent-finished@.service"

systemctl --user daemon-reload
