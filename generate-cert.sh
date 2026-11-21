#!/bin/sh
set -eu
dir="${1:-certs}"
mkdir -p "$dir"
umask 077
if [ -s "$dir/tls.key" ] && openssl x509 -in "$dir/tls.crt" -checkend 86400 -noout 2>/dev/null; then
    exit 0
fi
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 365 \
    -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    -keyout "$dir/tls.key.tmp" -out "$dir/tls.crt.tmp"
mv "$dir/tls.key.tmp" "$dir/tls.key"
mv "$dir/tls.crt.tmp" "$dir/tls.crt"
