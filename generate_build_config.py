#!/usr/bin/env python
from __future__ import print_function

import argparse
import base64
import sys


TEMPLATE = """\
#cloud-config
packages:
- bzr
- squashfs-tools
- python-setuptools
- python-twisted
- dpkg-dev
runcmd:
# Setup environment
- export HOME={homedir}
- export BUILD_ID=root
- export CHROOT_ROOT={homedir}/build-$BUILD_ID/chroot-autobuild

# Setup build chroot
- wget http://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64.squashfs -O /tmp/root.squashfs
- mkdir -p $CHROOT_ROOT
- unsquashfs -force -no-progress -dest $CHROOT_ROOT /tmp/root.squashfs
- mkdir $CHROOT_ROOT/build
- rm $CHROOT_ROOT/etc/resolv.conf  # We need to write over this symlink

# Pull in build scripts and install the python parts
- bzr branch lp:launchpad-buildd {homedir}/launchpad-buildd
- "pushd .; cd /home/ubuntu/launchpad-buildd; python setup.py install; popd"

# Perform the build
- {homedir}/launchpad-buildd/bin/mount-chroot $BUILD_ID
{ppa_conf}
- {homedir}/launchpad-buildd/bin/update-debian-chroot $BUILD_ID
- "{homedir}/launchpad-buildd/bin/buildlivefs --arch amd64 --project ubuntu-cpc --series xenial --build-id $BUILD_ID --datestamp ubuntu-standalone-builder-$(date +%s) {image_ppa}"
- {homedir}/launchpad-buildd/bin/umount-chroot $BUILD_ID
- mkdir {homedir}/images
- mv $CHROOT_ROOT/build/livecd.ubuntu-cpc.* {homedir}/images
"""  # noqa: E501

WRITE_FILES_STANZA_TEMPLATE = """\
- encoding: b64
  content: {content}
  path:
    {homedir}/build-root/chroot-autobuild/usr/share/livecd-rootfs/live-build/ubuntu-cpc/hooks/{sequence}-local-modifications.{hook_type}
  owner: root:root
  permissions: '0755'
"""  # noqa: E501

PRIVATE_PPA_TEMPLATE = """
- chroot $CHROOT_ROOT apt-get install -y apt-transport-https
- "echo 'deb {ppa_url} xenial main' | tee $CHROOT_ROOT/etc/apt/sources.list.d/builder-extra-ppa.list"
- "chroot $CHROOT_ROOT apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys {key_id}"
- chroot $CHROOT_ROOT apt-get -y update
"""  # noqa: E501

BINARY_HOOK_FILTER_CONTENT = """\
#!/bin/sh -eux
for hook in /build/config/hooks/*.binary; do
    case $(basename $hook) in
        {}|9997*|9998*|9999*)
            ;;
        *)
            cat << EOF > $hook
#!/bin/sh
echo "Skipped \$0"
exit 0
EOF
            ;;
    esac
done
"""

SETUP_CONTENT = """\
#!/bin/sh -eux
mv /usr/sbin/grub-probe /usr/sbin/grub-probe.dist
cat <<"PSEUDO_GRUB_PROBE" > /usr/sbin/grub-probe
#!/bin/sh
bad_Usage() { echo "$@"; exit 1; }

short_opts=""
long_opts="device-map:,target:,device"
getopt_out=$(getopt --name "${0##*/}" \
   --options "${short_opts}" --long "${long_opts}" -- "$@") &&
   eval set -- "${getopt_out}" ||
   bad_Usage

device_map=""
target=""
device=0
arg=""

while [ $# -ne 0 ]; do
   cur=${1}; next=${2};
   case "$cur" in
      --device-map) device_map=${next}; shift;;
      --device) device=1;;
      --target) target=${next}; shift;;
      --) shift; break;;
   esac
   shift;
done
arg=${1}

case "${target}:${device}:${arg}" in
   device:*:/*) echo "/dev/sda1"; exit 0;;
   fs:*:*) echo "ext2"; exit 0;;
   partmap:*:*) echo "msdos"; exit 0;;
   abstraction:*:*) echo ""; exit 0;;
   drive:*:/dev/sda) echo "(hd0)";;
   drive:*:/dev/sda*) echo "(hd0,1)";;
   fs_uuid:*:*) exit 1;;
esac
PSEUDO_GRUB_PROBE
chmod +x /usr/sbin/grub-probe
"""  # noqa: E501

TEARDOWN_CONTENT = """\
#!/bin/sh -eux
mv /usr/sbin/grub-probe.dist /usr/sbin/grub-probe
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
    if ppa.startswith("https://") and 'private-ppa' in ppa:
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
                         ' or be an "https://" URL pointing to a private PPA.')
    return conf


def _produce_write_files_stanza(content, hook_type, sequence, homedir):
    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    return WRITE_FILES_STANZA_TEMPLATE.format(
        content=b64_content, hook_type=hook_type, sequence=sequence,
        homedir=homedir)


def _write_cloud_config(output_file, binary_customisation_script=None,
                        binary_hook_filter=None, customisation_script=None,
                        build_ppa=None, build_ppa_key=None, homedir=None,
                        image_ppa=None):
    """
    Write an image building cloud-config file to a given location.

    :param output_file:
        An open file object to write the output to.
    :param binary_customisation_script:
        An (optional) path to a binary customisation script; this will be
        included as a binary hook in the build environment before it starts,
        allowing the built images to be manipulated.
    :param binary_hook_filter:
        An optional string that defines which binary hooks within the build
        chroot should be preserved.  This is templated in to a shell script, so
        globs valid in that context are valid here.  If not passed (and by
        default), all binary hooks are preserved.
    :param customisation_script:
        An (optional) path to a customisation script; this will be included as
        a chroot hook in the build environment before it starts, allowing
        modifications to the image contents to be made.
    :param homedir:
        An (optional) path to use for the build environment within the cloud
        instance.
    :param build_ppa:
        An (optional) URL pointing to either a public (ppa:user/repo) or
        private (https://user:pass@private-ppa.launchpad.net/...) PPA. This
        will be injected in the builder's chroot.
    :param build_ppa_key:
        The (optional) hexadecimal key ID used to sign the builder PPA. This
        is only used if "build_ppa" points to a private PPA, and is ignored in
        every other case.
    :param image_ppa:
        The identifier for a PPA to be injected inside the built image,
        optionally with a pin-priority. Archives have a priority of 500 by
        default, anything above this will take pinning precedence. Example:
        foo/bar:1001
    """
    ppa_snippet = ""
    if build_ppa is not None:
        ppa_snippet = _get_ppa_snippet(build_ppa, build_ppa_key)
    if homedir is None:
        homedir = '/home/ubuntu'
    if image_ppa is None:
        image_ppa_command = ''
    else:
        image_ppa_command = '--extra-ppa {}'.format(image_ppa)
    output_string = TEMPLATE.format(ppa_conf=ppa_snippet, homedir=homedir,
                                    image_ppa=image_ppa_command)
    write_files_stanzas = []
    for hook_type, script in (('chroot', customisation_script),
                              ('binary', binary_customisation_script)):
        if script is None:
            continue
        with open(script, 'rb') as f:
            content = f.read().decode('utf-8')
        if not content:
            continue
        if hook_type == 'chroot':
            write_files_stanzas.append(_produce_write_files_stanza(
                content=SETUP_CONTENT, hook_type=hook_type, sequence=9997,
                homedir=homedir))
            write_files_stanzas.append(_produce_write_files_stanza(
                content=TEARDOWN_CONTENT, hook_type=hook_type, sequence=9999,
                homedir=homedir))
        write_files_stanzas.append(_produce_write_files_stanza(
            content=content, hook_type=hook_type, sequence=9998,
            homedir=homedir))
    if binary_hook_filter is not None:
        write_files_stanzas.append(_produce_write_files_stanza(
            content=BINARY_HOOK_FILTER_CONTENT.format(binary_hook_filter),
            hook_type='binary',
            sequence=0,
            homedir=homedir))
    if write_files_stanzas:
        output_string += '\nwrite_files:\n'
        for stanza in write_files_stanzas:
            output_string += stanza
    output_file.write(output_string)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'),
                        default=sys.stdout)
    parser.add_argument('--binary-customisation-script',
                        dest='binary_custom_script',
                        help='A path to a script which will be run outside of'
                        'the image chroot, to modify the way the contents are'
                        ' packed in to image files.')
    parser.add_argument('--binary-customization-script',
                        dest='binary_custom_script', help=argparse.SUPPRESS)
    parser.add_argument('--binary-hook-filter',
                        dest='binary_hook_filter',
                        help='A glob which will be used to remove binary'
                        ' hooks from within the build chroot.  If not'
                        ' specified, no binary hooks will be removed.')
    parser.add_argument('--customisation-script', dest='custom_script',
                        help='A path to a script which will be run within'
                        ' the image chroot, to modify the content within the'
                        ' images produced.')
    parser.add_argument('--customization-script',
                        dest='custom_script', help=argparse.SUPPRESS)
    parser.add_argument('--homedir', dest='homedir', metavar='PATH',
                        help='The path within the image where the build should'
                        ' be done')
    parser.add_argument('--build-ppa', dest='build_ppa', help='The URL of a '
                        'PPA to inject in the build chroot. This can be '
                        'either a ppa:<user>/<ppa> short URL or an https:// '
                        'URL in the case of private PPAs. Example: '
                        '"ppa:foo/bar" or "https://user:password@host/ubuntu"')
    parser.add_argument('--build-ppa-key', dest='build_ppa_key', help='The '
                        'GPG key ID with which the passed build PPA was '
                        'signed. This is only needed for private (https://) '
                        'PPAs.')
    parser.add_argument('--image-ppa', dest='image_ppa', help='The identifier '
                        'for a public PPA to inject into the built image. '
                        'Optionally this can specify an apt pin priority for '
                        'the whole PPA. Example: "foo/bar:1001". Note the '
                        'absence of "~".')
    args = parser.parse_args()

    _write_cloud_config(args.outfile,
                        homedir=args.homedir,
                        customisation_script=args.custom_script,
                        binary_customisation_script=args.binary_custom_script,
                        binary_hook_filter=args.binary_hook_filter,
                        build_ppa=args.build_ppa,
                        build_ppa_key=args.build_ppa_key,
                        image_ppa=args.image_ppa)


if __name__ == '__main__':
    main()
