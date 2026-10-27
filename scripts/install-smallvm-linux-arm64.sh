#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
umask 077
fail() { printf 'SmallVM installation failed: %s\n' "$*" >&2; exit 1; }
usage() { printf '%s\n' 'Usage: install-smallvm-linux-arm64.sh --version VERSION --sha256 HEX [--archive FILE] [--prefix DIR] [--data-dir DIR] [--service] [--verify-only]'; }
version='' digest='' archive='' prefix="${HOME:?}/.local" data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/microblocks" service=0 verify_only=0
while (($#)); do
  case "$1" in
    --version|--sha256|--archive|--prefix|--data-dir) (($# >= 2)) || fail "Missing value for $1"; key=$1; value=$2; shift 2
      case "$key" in --version) version=$value;; --sha256) digest=$value;; --archive) archive=$value;; --prefix) prefix=$value;; --data-dir) data_dir=$value;; esac;;
    --service) service=1; shift;; --verify-only) verify_only=1; shift;;
    -h|--help) usage; exit 0;; *) fail "Unknown argument: $1";;
  esac
done
[[ $version =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ && $version != latest ]] || fail 'A pinned version is required'
[[ $digest =~ ^[a-fA-F0-9]{64}$ ]] || fail 'An independent SHA-256 archive digest is required'
[[ $(uname -s) == Linux ]] || fail 'Requires Linux'
if ((!verify_only)); then
  [[ $(uname -m) == aarch64 ]] || fail 'Requires native AArch64 Linux (64-bit OS)'
  [[ $EUID -ne 0 ]] || fail 'Run as the intended unprivileged user; root installation is not supported'
fi
for command in python3 sha256sum tar mktemp df install sed head awk stat cp cmp mv grep chmod; do command -v "$command" >/dev/null || fail "Missing dependency: $command"; done
[[ $prefix == /* && $data_dir == /* && $prefix != / && $data_dir != / ]] || fail 'Install and data paths must be absolute non-root directories'
[[ ! $prefix =~ [[:cntrl:]] && ! $data_dir =~ [[:cntrl:]] && $prefix != *'$'* && $data_dir != *'$'* && $prefix != *'"'* && $data_dir != *'"'* && $prefix != *'%'* && $data_dir != *'%'* && $prefix != *'\'* && $data_dir != *'\'* ]] || fail 'Unsupported characters in paths'
[[ -r /etc/os-release ]] || fail 'Linux distribution metadata is unavailable'
printf 'Platform: %s / %s\n' "$(uname -m)" "$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | head -1)"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
available=$(df -Pk "$work" | awk 'NR==2 {print $4}')
[[ $available =~ ^[0-9]+$ && $available -ge 131072 ]] || fail 'At least 128 MiB temporary disk space is required'
if [[ -z $archive ]]; then
  command -v curl >/dev/null || fail 'Missing dependency: curl'
  archive="$work/release.tar.gz"
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --max-filesize 67108864 \
    "https://github.com/speccy88/microblocks-zephyr/releases/download/$version/smallvm-linux-arm64-$version.tar.gz" -o "$archive"
fi
[[ -f $archive && ! -L $archive ]] || fail 'Archive must be a regular file'
[[ $(stat -c %s -- "$archive") -le 67108864 ]] || fail 'Archive exceeds the 64 MiB size limit'
actual=$(sha256sum -- "$archive"); actual=${actual%% *}
[[ ${actual,,} == ${digest,,} ]] || fail 'Release checksum mismatch; nothing installed'
mkdir "$work/package"
python3 - "$archive" "$work/package" "$version" <<'PY'
import json, pathlib, struct, sys, tarfile
archive, destination, version = sys.argv[1:]
allowed = {'smallvm', 'manifest.json', 'LICENSE', 'NOTICE'}
with tarfile.open(archive, 'r:gz') as bundle:
    members = bundle.getmembers()
    names = [m.name for m in members]
    if len(names) != len(set(names)) or not {'smallvm', 'manifest.json', 'LICENSE'} <= set(names) or not set(names) <= allowed:
        raise SystemExit('Invalid package member set')
    if any(not m.isfile() or m.size > 32 * 1024 * 1024 for m in members) or sum(m.size for m in members) > 64 * 1024 * 1024:
        raise SystemExit('Unsupported package member or size')
    metadata = json.load(bundle.extractfile('manifest.json'))
    if metadata.get('version') != version or metadata.get('architecture') != 'linux-aarch64' or metadata.get('source_commit') != '2071df569623ba9cdcd6f8106b61796e047df38b':
        raise SystemExit('Package identity/source mismatch')
    binary = bundle.extractfile('smallvm').read()
    if len(binary) < 64 or binary[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', binary, 18)[0] != 183:
        raise SystemExit('Expected a little-endian ELF64 AArch64 executable')
    for member in members:
        target = pathlib.Path(destination) / member.name
        target.write_bytes(bundle.extractfile(member).read())
        target.chmod(0o700 if member.name == 'smallvm' else 0o600)
print('Archive checksum, layout, pinned source and AArch64 ELF identity verified')
PY
if ((verify_only)); then printf 'Verification only; executable not run and no installation changed.\n'; exit 0; fi
[[ ! -L $data_dir ]] || fail 'Refusing a symlink program data directory'
[[ ! -e $data_dir || ( -d $data_dir && -O $data_dir ) ]] || fail 'Program data directory must belong to the installing user'
if ((service)); then
  command -v systemctl >/dev/null || fail 'systemd is required for --service'
  systemctl --user show-environment >/dev/null || fail 'No user systemd manager; retry without --service'
fi
command_path="$prefix/bin/smallvm"
[[ ! -L $command_path ]] || fail 'Refusing to replace a symlink launcher'
if [[ -e $command_path ]]; then
  [[ -f $command_path ]] && grep -q '^# microblocks-linux-arm64-v1$' "$command_path" || fail 'Refusing to replace unrelated smallvm command'
fi
release_dir="$prefix/lib/microblocks/$version"
[[ ! -L $release_dir ]] || fail 'Refusing to install through a symlink release'
[[ ! -L $release_dir/smallvm ]] || fail 'Refusing to reuse a symlink executable'
if [[ -e $prefix/lib/microblocks/INSTALLATION ]]; then
  [[ ! -L $prefix/lib/microblocks/INSTALLATION && $(cat "$prefix/lib/microblocks/INSTALLATION") == microblocks-linux-arm64-v1 ]] || fail 'Unrecognized installation marker'
fi
if ((service)); then
  unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  unit="$unit_dir/microblocks-smallvm.service"
  [[ ! -L $unit ]] || fail 'Refusing to replace a symlink service'
  if [[ -e $unit ]]; then
    grep -q '^# microblocks-linux-arm64-v1$' "$unit" && grep -Fxq -- "# microblocks-prefix=$prefix" "$unit" || fail 'Refusing to replace a service belonging to another prefix'
  fi
fi
# A real release must implement this bounded, side-effect-free startup check.
command -v timeout >/dev/null || fail 'Missing dependency: timeout'
(cd "$work" && timeout 10 "$work/package/smallvm" --self-test) || fail 'Executable self-test failed; installed version preserved'
mkdir -p "$prefix/lib/microblocks" "$prefix/bin" "$data_dir"
chmod 700 "$data_dir"
if [[ -e $release_dir ]]; then
  for identity_file in smallvm manifest.json LICENSE; do
    [[ -f $release_dir/$identity_file && ! -L $release_dir/$identity_file ]] && cmp -s "$work/package/$identity_file" "$release_dir/$identity_file" || fail 'Version already installed with different binary/manifest/license identity'
  done
  if [[ -f $work/package/NOTICE ]]; then
    [[ -f $release_dir/NOTICE && ! -L $release_dir/NOTICE ]] && cmp -s "$work/package/NOTICE" "$release_dir/NOTICE" || fail 'Version already installed with different notices'
  fi
else
  # Stage on the target filesystem, so publication is an atomic directory rename.
  staged=$(mktemp -d "$prefix/lib/microblocks/.install.XXXXXX")
  cp -p "$work/package/"* "$staged/"
  mv -- "$staged" "$release_dir"
fi
printf 'microblocks-linux-arm64-v1\n' > "$prefix/lib/microblocks/INSTALLATION"
python3 - "$prefix" "$data_dir" "$release_dir" <<'PY'
import os, pathlib, shlex, sys
prefix, data, release = map(pathlib.Path, sys.argv[1:])
target = prefix / 'bin/smallvm'
executable = shlex.quote(str(release / 'smallvm'))
text = ('#!/bin/sh\n# microblocks-linux-arm64-v1\nset -eu\n'
        'if [ "$#" -eq 1 ] && [ "$1" = --self-test ]; then\n  exec ' + executable + ' --self-test\nfi\n'
        'exec ' + executable + ' --data-dir ' + shlex.quote(str(data)) + ' "$@"\n')
if target.exists() and 'microblocks-linux-arm64-v1' not in target.read_text(errors='replace'):
    raise SystemExit('Refusing to replace an unrelated smallvm command')
temporary = target.with_name('.smallvm-install-' + str(os.getpid()))
temporary.write_text(text); temporary.chmod(0o700); os.replace(temporary, target)
PY
if ((service)); then
  mkdir -p "$unit_dir"
  cat > "$unit" <<EOF
# microblocks-linux-arm64-v1
# microblocks-prefix=$prefix
[Unit]
Description=MicroBlocks SmallVM (user session)
[Service]
ExecStart="$prefix/bin/smallvm"
WorkingDirectory="$data_dir"
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths="$data_dir"
[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now microblocks-smallvm.service
  systemctl --user restart microblocks-smallvm.service
  systemctl --user is-active --quiet microblocks-smallvm.service || fail 'Installed, but user service is not active'
fi
printf 'Installed %s at %s; programs retained in %s\n' "$version" "$prefix/bin/smallvm" "$data_dir"
printf 'No network listener configured. User service startup requires an active user manager; boot without login is not enabled.\n'
