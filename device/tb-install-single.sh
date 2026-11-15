#!/bin/bash
# Experimental source only. Never install until integration and hardware tests pass.
# Single-system installation erases userdata/arch. It requires an NBD root.
set -euo pipefail
fail() { echo "INSTALL FAILED: $*" >&2; exit 1; }
[ "${TB710FU_ENABLE_UNTESTED_INSTALLER:-}" = yes ] || fail 'Untested development code is disabled'
[ "$(id -u)" = 0 ] || fail 'root privileges required'
for cmd in findmnt lsblk sgdisk blockdev mkfs.ext4 rsync sha256sum dd mount umount python3 partprobe swapon reboot; do
  command -v "$cmd" >/dev/null || fail "missing tool: $cmd"
done
model=$(tr '\0' ' ' </sys/firmware/devicetree/base/model)
[[ "$model" == *TB710FU* ]] || fail 'not a TB710FU'
[[ " $(cat /proc/cmdline) " == *' tb710fu.install=single '* ]] || fail 'not booted in single install mode'
root=$(findmnt -n -o SOURCE /)
[ "$root" = /dev/nbd0p2 ] || fail 'installer root is not the expected NBD partition'
[ -b /dev/nbd0p1 ] || fail 'NBD control partition missing'
[ "$(blockdev --getsize64 /dev/nbd0p1)" = 134217728 ] || fail 'unexpected control partition size'
request=$(dd if=/dev/nbd0p1 bs=512 count=1 status=none | tr -d '\000' | head -n 1)
[[ "$request" =~ ^TB710FU-REQUEST:([0-9a-f]{32}):([0-9a-f]{64}):100663296$ ]] || fail 'invalid host installation request'
nonce=${BASH_REMATCH[1]}
expected=${BASH_REMATCH[2]}
# Menu-label variant retains the verified original Ubuntu kernel and DTB.
[ "$expected" = 820d71fce5046b594a0c802623e9a658b3b6f6fa0f976f0090c6f76e9b8258c9 ] || fail 'boot image does not match the verified Ubuntu menu variant'
boot_image=/run/tb710fu-final-boot.img
[ ! -e "$boot_image" ] || fail 'temporary boot image already exists'
umask 077
dd if=/dev/nbd0p1 of="$boot_image" bs=4096 skip=1 count=24576 status=none || fail 'could not read host boot image'
[ "$(stat -c %s "$boot_image")" = 100663296 ] || fail 'truncated boot image'
[ "$(sha256sum "$boot_image" | awk '{print $1}')" = "$expected" ] || fail 'boot checksum mismatch'
for file in /usr/lib/firmware/qcom/sm8650/xiaoxin/gt/adsp.mbn /usr/lib/firmware/qcom/sm8650/xiaoxin/gt/cdsp.mbn /usr/lib/firmware/ath12k/WCN7850/hw2.0/amss.bin; do
  [ -s "$file" ] || fail 'device firmware missing; refusing before disk changes'
done
[ -x /usr/libexec/gnome-initial-setup ] || fail 'first-run setup missing'
# Resolve a unique GPT label from sysfs, refusing duplicate labels.
partdev() {
  local wanted=$1 p result='' count=0
  for p in /sys/class/block/sd*; do
    [ -f "$p/partition" ] && [ -r "$p/uevent" ] || continue
    if grep -Fxq "PARTNAME=$wanted" "$p/uevent"; then result=/dev/${p##*/}; count=$((count+1)); fi
  done
  [ "$count" -le 1 ] || return 1
  printf '%s\n' "$result"
}
arch=$(partdev arch) || fail 'duplicate arch partitions'
userdata=$(partdev userdata) || fail 'duplicate userdata partitions'
[ -z "$arch" ] || [ -z "$userdata" ] || fail 'existing dual layout requires manual review'
target=${arch:-$userdata}
[ -n "$target" ] && [ -b "$target" ] || fail 'no unique target partition'
parent=$(lsblk -ndo PKNAME "$target")
[[ "$parent" =~ ^sd[a-z]+$ ]] || fail 'unexpected target disk'
disk=/dev/$parent
number=$(cat "/sys/class/block/${target##*/}/partition")
[[ "$number" =~ ^[1-9][0-9]*$ ]] || fail 'unexpected partition number'
[ "$(blockdev --getss "$disk")" = 4096 ] || fail 'unexpected sector size'
[ "$(blockdev --getsize64 "$target")" -ge 34359738368 ] || fail 'target is smaller than 32 GiB'
for entry in /sys/class/block/"$parent"*; do
  [ -f "$entry/partition" ] || continue
  candidate=/dev/${entry##*/}
  if findmnt -rn -S "$candidate" | grep -q .; then fail 'a partition on the target disk is mounted'; fi
  if swapon --noheadings --raw --output NAME | grep -Fxq "$candidate"; then fail 'a partition on the target disk is active swap'; fi
done
boot=$(partdev boot_a) || fail 'duplicate boot_a partitions'
[ -n "$boot" ] && [ -b "$boot" ] || fail 'boot_a is not a block device'
size=$(stat -c %s "$boot_image")
[ "$size" -eq "$(blockdev --getsize64 "$boot")" ] || fail 'boot image size mismatch'
[ $((size % 4194304)) -eq 0 ] || fail 'boot size is not aligned'
sgdisk --verify "$disk" >/dev/null || fail 'GPT verification failed'
mkdir -p -m 700 /root/tb-install-backup
[ ! -e /root/tb-install-backup/gpt-before.bin ] || fail 'backup already exists'
sgdisk --backup=/root/tb-install-backup/gpt-before.bin "$disk" || fail 'GPT backup failed'
[ -s /root/tb-install-backup/gpt-before.bin ] || fail 'empty GPT backup'
# The host request has been checked and all required inputs exist. This is the
# first destructive operation; the old userdata or arch contents are erased.
if [ -n "$userdata" ]; then
  sgdisk --change-name="$number:arch" --typecode="$number:8300" "$disk" || fail 'GPT rename failed'
  partprobe "$disk" || fail 'partition table rescan failed'
  [ "$(partdev arch)" = "$target" ] || fail 'renamed partition was not verified'
fi
mkfs.ext4 -F -L ubuntu-root "$target" || fail 'filesystem creation failed'
mkdir -p /mnt/tb-install-target
mount -o noatime "$target" /mnt/tb-install-target || fail 'target mount failed'
trap 'umount /mnt/tb-install-target 2>/dev/null || true' EXIT
rsync -aHAXx --numeric-ids --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/run --exclude=/tmp --exclude=/mnt --exclude=/media --exclude=/var/tmp --exclude=/var/log --exclude=/var/cache --exclude=/etc/machine-id --exclude='/etc/ssh/ssh_host_*' --exclude=/var/lib/systemd/random-seed --exclude=/boot/tbboot / /mnt/tb-install-target/ || fail 'system copy failed'
mkdir -p /mnt/tb-install-target/{proc,sys,dev,run,tmp,mnt,media,var/tmp,var/log,var/cache}
# The installed system must not retain an enabled installer.
rm -f /mnt/tb-install-target/etc/systemd/system/sysinit.target.wants/tb-installer.service /mnt/tb-install-target/etc/systemd/system/tb-installer.service /mnt/tb-install-target/usr/local/sbin/tb-install-single
chmod 1777 /mnt/tb-install-target/tmp /mnt/tb-install-target/var/tmp
: > /mnt/tb-install-target/etc/machine-id
sync
umount /mnt/tb-install-target
trap - EXIT
# Return to the supplied original Ubuntu boot/DT baseline; read back every byte.
dd if="$boot_image" of="$boot" bs=4M conv=fsync status=none || fail 'boot write failed'
actual=$(dd if="$boot" bs=4M count=$((size/4194304)) status=none | sha256sum | awk '{print $1}')
[ "$actual" = "$expected" ] || fail 'boot read-back mismatch'
sync
# The host recognises only a response for this installation's random nonce.
printf 'TB710FU-OK:%s\n' "$nonce" | dd of=/dev/nbd0p1 bs=512 count=1 conv=sync,fsync status=none || fail 'completion signal failed'
echo 'INSTALL_OK: rebooting into the installed system.'
sync
reboot -f
fail 'reboot command returned unexpectedly'
