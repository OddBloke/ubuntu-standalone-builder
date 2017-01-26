#!/usr/bin/env python
from __future__ import print_function

import base64
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

WRITE_FILES_TEMPLATE = """\
write_files:
- encoding: b64
  content: {content}
  path:
    /home/ubuntu/build-output/chroot-autobuild/usr/share/livecd-rootfs/live-build/ubuntu-cpc/hooks/9999-local-modifications.chroot
  owner: root:root
  permissions: '0755'
"""


def _write_cloud_config(output_file, customisation_script=None):
    """
    Write an image building cloud-config file to a given location.

    :param output_file:
        The path for the file to write to.
    :param customisation_script:
        An (optional) path to a customisation script; this will be included as a
        chroot hook in the build environment before it starts, allowing
        modifications to the image contents to be made.
    """
    output_string = TEMPLATE
    if customisation_script is not None:
        with open(customisation_script, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        if content:
            output_string += '\n'
            output_string += WRITE_FILES_TEMPLATE.format(content=content)
    with open(output_file, 'w') as f:
        f.write(output_string)


def main():
    if len(sys.argv) == 2:
        _write_cloud_config(sys.argv[1])
    elif len(sys.argv) == 3:
        _write_cloud_config(sys.argv[1], customisation_script=sys.argv[2])
    else:
        print('{} expects one or two arguments.'.format(sys.argv[0]))
        sys.exit(1)


if __name__ == '__main__':
    main()
