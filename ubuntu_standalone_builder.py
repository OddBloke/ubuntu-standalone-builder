TEMPLATE = """\
#cloud-config
packages:
- bzr
runcmd:
# Setup environment
- export HOME=/home/ubuntu
- export BUILD_ID=FIXME

# Setup build chroot
- wget http://cloud-images.ubuntu.com/releases/xenial/release/ubuntu-16.04-server-cloudimg-amd64-root.tar.xz -O /tmp/root.tar.xz
- mkdir -p /home/ubuntu/build-$BUILD_ID/chroot-autobuild
- tar -C /home/ubuntu/build-$BUILD_ID/chroot-autobuild -x -f /tmp/root.tar.xz
- mkdir /home/ubuntu/build-$BUILD_ID/chroot-autobuild/build
- rm /home/ubuntu/build-$BUILD_ID/chroot-autobuild/etc/resolv.conf  # We need to write over this symlink

# Pull in build scripts
- bzr branch lp:launchpad-buildd /home/ubuntu/launchpad-buildd

# Perform the build
- /home/ubuntu/launchpad-buildd/mount-chroot $BUILD_ID
- /home/ubuntu/launchpad-buildd/update-debian-chroot $BUILD_ID
- /home/ubuntu/launchpad-buildd/buildlivefs --arch amd64 --project ubuntu-cpc --series xenial --build-id $BUILD_ID
- /home/ubuntu/launchpad-buildd/umount-chroot $BUILD_ID
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
    pass


if __name__ == '__main__':
    main()
