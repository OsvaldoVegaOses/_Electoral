#!/bin/sh
set -eu
umask 077
case "${BELENIOS_VARDIR:-}" in /home/belenios/poc-data) ;; *) exit 2;; esac
mkdir -p "$BELENIOS_VARDIR/private"
cat >> "$BELENIOS_VARDIR/private/mail.txt"
