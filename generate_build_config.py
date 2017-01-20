#!/usr/bin/env python
from __future__ import print_function

import sys


TEMPLATE = """\
#cloud-config
packages:
- bzr
runcmd:
# Setup environment
- export HOME=/home/ubuntu
- export BUILD_ID=output
- export CHROOT_ROOT=/home/ubuntu/build-$BUILD_ID/chroot-autobuild

# Setup build chroot
- wget http://cloud-images.ubuntu.com/releases/xenial/release/ubuntu-16.04-server-cloudimg-amd64-root.tar.xz -O /tmp/root.tar.xz
- mkdir -p $CHROOT_ROOT
- tar -C $CHROOT_ROOT -x -f /tmp/root.tar.xz
- mkdir $CHROOT_ROOT/build
- rm $CHROOT_ROOT/etc/resolv.conf  # We need to write over this symlink

# Pull in build scripts
- bzr branch lp:launchpad-buildd /home/ubuntu/launchpad-buildd

# Perform the build
- /home/ubuntu/launchpad-buildd/mount-chroot $BUILD_ID
- /home/ubuntu/launchpad-buildd/update-debian-chroot $BUILD_ID
- /home/ubuntu/launchpad-buildd/buildlivefs --arch amd64 --project ubuntu-cpc --series xenial --build-id $BUILD_ID
- /home/ubuntu/launchpad-buildd/umount-chroot $BUILD_ID
- mkdir /home/ubuntu/images
- mv $CHROOT_ROOT/build/livecd.ubuntu-cpc.* /home/ubuntu/images
"""


def _write_cloud_config(output_file):
    """
    Write an image building cloud-config file to a given location.

    :param output_file:
        The path for the file to write to.
    """
    with open(output_file, 'w') as f:
        f.write(TEMPLATE)


def main():
    if len(sys.argv) != 2:
        print('{} expects exactly one argument.'.format(sys.argv[0]))
        sys.exit(1)
    _write_cloud_config(sys.argv[1])


if __name__ == '__main__':
    main()
