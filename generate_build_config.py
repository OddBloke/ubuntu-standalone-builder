#!/usr/bin/env python
from __future__ import print_function

import argparse
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
{ppa_conf}
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

PRIVATE_PPA_TEMPLATE = """
- chroot $CHROOT_ROOT apt install apt-transport-https
- "echo 'deb {ppa_url} xenial main' | tee $CHROOT_ROOT/etc/apt/sources.list.d/builder-extra-ppa.list"
- "chroot $CHROOT_ROOT apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys {key_id}"
- chroot $CHROOT_ROOT apt update
"""

def _get_ppa_snippet(ppa, ppa_key=None):
    """
    Depending on what string is passed as PPA, return an appropriate yaml
    snippet, ready to inject in TEMPLATE.

    :param ppa:
        The PPA URL. This should be either a "ppa:foo/bar" short form or a
        full https:// URL for private PPAs.
    :param ppa_key:
        The hexacecimal key ID used to sign the PPA's package. This is only
        used for private PPAs.
    """
    conf = ""
    if ppa.startswith("https://"):
        # This is likely a private PPA. We need to:
        # 1. Make sure apt-transport-https is installed.
        # 2. Add the URL to sources.list
        # 3. Add the signing key to the apt keyring.
        # 4. apt update
        if ppa_key is None:
            raise ValueError("You must provide a --ppa-key parameter if using "
                             "a private PPA URL.")
        conf = PRIVATE_PPA_TEMPLATE.format(ppa_url=ppa, key_id=ppa_key)
    elif ppa.startswith("ppa"):
        # The simple case, we simply need to inject an "add-apt-repository"
        # command.
        conf = '- chroot $CHROOT_ROOT add-apt-repository -y -u {}'.format(ppa)
    else:
        raise ValueError('The extra PPA url must be of the "ppa:foo/bar" form,'
                         ' or be an "https:" URL pointing to a private PPA.')
    return conf


def _write_cloud_config(output_file, customisation_script=None, ppa=None,
                        ppa_key=None):
    """
    Write an image building cloud-config file to a given location.

    :param output_file:
        The path for the file to write to.
    :param customisation_script:
        An (optional) path to a customisation script; this will be included as a
        chroot hook in the build environment before it starts, allowing
        modifications to the image contents to be made.
    :param ppa:
        An (optional) URL pointing to either a public (ppa:user/repo) or
        private (https://user:pass@private-ppa.launchpad.net/...) PPA.
    :param ppa_key:
        The (optional) hexadecimal key ID used to sign the PPA. This is only
        used if "ppa" points to a private PPA, and is ignored in every other
        case.
    """
    ppa_snippet = ""
    if ppa is not None:
        ppa_snippet = _get_ppa_snippet(ppa, ppa_key)
    output_string = TEMPLATE.format(ppa_conf=ppa_snippet)
    if customisation_script is not None:
        with open(customisation_script, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        if content:
            output_string += '\n'
            output_string += WRITE_FILES_TEMPLATE.format(content=content)
    with open(output_file, 'w') as f:
        f.write(output_string)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output_filename')
    parser.add_argument('--customisation-script', dest='custom_script')
    parser.add_argument('--ppa', dest='ppa', help='The URL of a PPA to inject '
                        'in the build chroot. This can be either a '
                        'ppa:<user>/<ppa> short URL or an https:// URL in the '
                        'case of private PPAs.')
    parser.add_argument('--ppa-key', dest='ppa_key', help='The GPG key ID '
                        'with which the passed PPA was signed. This is only '
                        'needed for private (https://) PPAs.')
    args = parser.parse_args()

    _write_cloud_config(args.output_filename, ppa=args.ppa,
                        customisation_script=args.custom_script,
                        ppa_key=args.ppa_key)


if __name__ == '__main__':
    main()
