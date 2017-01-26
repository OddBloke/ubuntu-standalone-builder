# ubuntu-standalone-builder

[![Travis status](https://travis-ci.org/OddBloke/ubuntu-standalone-builder.svg?branch=master)](https://travis-ci.org/OddBloke/ubuntu-standalone-builder)

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
that we will pass in to our cloud instance.  In the basic case, it
takes a single argument that specifies the output location:

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
* it will run cloud-init on boot,
* it supports passing user-data through to instances, and
* it has at least a 20G root disk.

The first three conditions are met by the Ubuntu images published in
all major clouds, and on
[cloud-images.ubuntu.com](http://cloud-images.ubuntu.com), and the
fourth can be met when launching an instance.  Below we
show specific examples of how to launch instances with `cloud-config`
and an appropriately-sized disk.

#### Microsoft Azure

In order to launch a Microsoft Azure instance with the build
`cloud-config`, run the following command:

```
$ azure vm quick-create \
    --custom-data build-config.yaml \
    --image-urn canonical:ubuntuserver:16.04-LTS:latest \
    --admin-username ubuntu \
    --os-type Linux
```

You may also want to specify an SSH key that will be placed on the
instance, so you don't have to type out a password so often.  To do
this, append the following to your command:

```
    --ssh-publickey-file <path to SSH public key>
```

All of the above assumes that you are using [Azure Resource
Manager](https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-overview),
and will prompt you for the other arguments required to launch your VM.

(The default Ubuntu image on Microsoft Azure has a root disk of 30GB, so
no additional configuration is required in order to have enough disk
space for the build.)

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

## Customising the Built Images

In order to customise the contents of the built images, you can provide
a second argument to `generate_build_config.py`.  This should be the
path to a shell script which will be run within the chroot after all
other image building is complete.

For example, if you wanted RabbitMQ server to be installed in all the
images that are produced, you could write a shell script that looked
something like this out to `script.sh`:

```
#!/bin/sh
apt-get update -qqy
apt-get install -qqy rabbitmq-server
```

And then, when generating your cloud-config, you simply pass this to
`generate_build_config.py`:

```
$ ./generate_build_config.py build-config.yaml script.sh
```

You can then pass `build-config.yaml` in to your instance launch as
normal, and you'll get your customised images.
