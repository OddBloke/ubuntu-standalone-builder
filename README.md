# ubuntu-standalone-builder
Build Ubuntu images independent of Launchpad's infrastructure

## How To Build Images

Building images using ubuntu-standalone builder is a three-phase process:

* Firstly, we generate
  [cloud-config](http://cloudinit.readthedocs.io/en/latest/topics/format.html#cloud-config-data)
  that will produce an image that matches our specification,
* Secondly, we launch a cloud instance with this cloud-config that will
  then perform the build, and
* Finally, we fetch the images from the machine.

### Generating cloud-config

The `generate_build_config.py` tool is used to produce the cloud-config
that we will pass in to our cloud instance.  Currently, it takes a
single argument that specifies the output location:

```
$ ./generate_build_config.py build-config.yaml
```

The cloud-config it produces will build the artifacts that are found on
[cloud-images.ubuntu.com](http://cloud-images.ubuntu.com) for xenial.

### Launching a build instance

ubuntu-standalone-builder allows you to launch cloud instances to
perform the build in any way you wish.  It is assumed that the
following is true of the instance you choose to launch:

* it is running Ubuntu 16.04 (xenial) or later,
* it will run cloud-init on boot, and
* it supports passing user-data through to instances.

These conditions are met by the Ubuntu images published in all major
clouds, and on
[cloud-images.ubuntu.com](http://cloud-images.ubuntu.com).  Below we
show specific examples of how to launch instances with `cloud-config`.

#### Microsoft Azure

In order to launch a Microsoft Azure instance with the build
`cloud-config`, run the following command:

```
$ azure vm quick-create \
    --custom-data build-config.yaml \
    --image-urn canonical:ubuntuserver:16.04-LTS:latest
```

This assumes that you are using [Azure Resource
Manager](https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-overview),
and will prompt you for the other arguments required to launch your VM.

### Tracking build progress

When your build instance launches, cloud-init will start performing the
build in the background.  If you want to see the output from the build
process, you can tail cloud-init's output:

```
$ tail -f /var/log/cloud-init-output.log
```

The final thing that the build process does is to move the built images
in to `/home/ubuntu/images`; you can tell that the build is complete
once image files are placed there.

### Fetching built images

Once the image build process has completed, you will find the image
build artifacts in `/home/ubuntu/images`; the files will have
`livecd.ubuntu-cpc.` as their prefix.

To fetch, for example, the root squashfs, you can simply use `scp`:

```
$ scp ubuntu@<INSTANCE>:images/livecd.ubuntu-cpc.squashfs .
```
