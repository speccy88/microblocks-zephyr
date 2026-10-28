#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
prefix="${HOME:?}/.local"
if (($#)); then [[ $# == 2 && $1 == --prefix ]] || { echo 'Usage: uninstall-smallvm-linux-arm64.sh [--prefix DIR]' >&2; exit 1; }; prefix=$2; fi
[[ $EUID -ne 0 && $prefix == /* && $prefix != / ]] || { echo 'Use an unprivileged account and an absolute non-root prefix' >&2; exit 1; }
[[ ! $prefix =~ [[:cntrl:]] && $prefix != *'$'* && $prefix != *'"'* && $prefix != *'%'* && $prefix != *'\'* ]] || { echo 'Unsupported characters in prefix' >&2; exit 1; }
marker="$prefix/lib/microblocks/INSTALLATION"
[[ -f $marker && ! -L $marker && $(cat "$marker") == microblocks-linux-arm64-v1 ]] || { echo 'No managed installation at this prefix' >&2; exit 1; }
unit="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/microblocks-smallvm.service"
if [[ -f $unit && ! -L $unit ]] && grep -q '^# microblocks-linux-arm64-v1$' "$unit" && grep -Fxq -- "# microblocks-prefix=$prefix" "$unit"; then
  command -v systemctl >/dev/null || { echo 'systemctl required to remove managed service' >&2; exit 1; }
  if ! systemctl --user disable --now microblocks-smallvm.service; then
    # A rejected unit can be inactive but not stoppable. Do not remove files
    # after an uncertain stop: independently require a reachable manager,
    # an inactive/failed state and no remaining main process.
    state=$(systemctl --user show microblocks-smallvm.service -p ActiveState -p MainPID) || exit 1
    if ! grep -Eq '^ActiveState=(inactive|failed)$' <<< "$state" || ! grep -Fxq 'MainPID=0' <<< "$state"; then
      echo 'Managed service stop not confirmed; unit and launcher retained' >&2
      exit 1
    fi
  fi
  rm -- "$unit"
  systemctl --user daemon-reload
fi
command_path="$prefix/bin/smallvm"
if [[ -f $command_path ]] && grep -q '^# microblocks-linux-arm64-v1$' "$command_path"; then rm -- "$command_path"; fi
printf 'Managed launcher/service removed. Programs and versioned binaries retained for recovery at %s.\n' "$prefix/lib/microblocks"
