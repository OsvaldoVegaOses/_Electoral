#!/bin/sh
set -eu
umask 077
: "${POC_PUBLIC_URL:?POC_PUBLIC_URL required}"
case "$POC_PUBLIC_URL" in
  http://127.0.0.1:18001|http://127.0.0.1:18002) ;;
  *) echo 'Only the two approved loopback laboratory URLs are allowed' >&2; exit 2;;
esac
case "${POC_DENY_REVOTE:-false}" in true) REVOTE='<deny-revote/>';; false) REVOTE='';; *) exit 2;; esac
mkdir -p "$BELENIOS_VARDIR/private"
printf '%s\n' poc-admin > "$BELENIOS_VARDIR/private/admin-allowlist"
cat > "$BELENIOS_CONFIG" <<EOF
<ocsigen><server>
  <port>0.0.0.0:8001</port>
  <mimefile>_SHAREDIR_/mime.types</mimefile>
  <logdir>_VARDIR_/log</logdir><datadir>_VARDIR_/lib</datadir>
  <uploaddir>_VARDIR_/upload</uploaddir>
  <maxuploadfilesize>5120kB</maxuploadfilesize><maxconnected>100</maxconnected>
  <commandpipe>_RUNDIR_/ocsigenserver_command</commandpipe><charset>utf-8</charset>
  <extension name="staticmod"/><extension name="redirectmod"/>
  <extension name="ocsipersist"><database file="_VARDIR_/lib/ocsidb"/></extension>
  <extension name="eliom"/>
  <host charset="utf-8" hostfilter="*" defaulthostname="localhost">
    <site path="static" charset="utf-8"><static dir="_SHAREDIR_/static" cache="0"/></site>
    <eliom name="belenios">
      <public-url prefix="$POC_PUBLIC_URL"/>
      <domain name="ejemplo.test"/>
      <maxrequestbodysizeinmemory value="1048576"/><maxmailsatonce value="100"/>
      <tos uri="$POC_PUBLIC_URL/"/>
      <server mail="urna@ejemplo.test" return-path="rebotes@ejemplo.test" name="Laboratorio sintetico" senderid="poc"/>
      <auth-export name="email"><email/></auth-export>
      <auth-export name="demo"><dummy/></auth-export>
      <auth name="demo"><dummy allowlist="poc_admins"/></auth>
      <source file="_SHAREDIR_/belenios.tar.gz"/>
      <default-group group="Ed25519"/><nh-group group="Ed25519"/>
      <share dir="_SHAREDIR_"/>
      <storage backend="filesystem">
        <uuid length="14"/><spool dir="_VARDIR_/spool"/><accounts dir="_VARDIR_/accounts"/>
        <map from="poc_admins" to="_VARDIR_/private/admin-allowlist"/>
      </storage>
      $REVOTE
    </eliom>
  </host>
</server></ocsigen>
EOF
exec ./demo/run-server.sh
