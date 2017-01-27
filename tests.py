import base64

import py
import pytest
import yaml

import generate_build_config


class TestWriteCloudConfig(object):

    def test_writes_to_file(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        generate_build_config._write_cloud_config(output_file.strpath)
        assert output_file.check()

    def test_written_output_is_yaml(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        generate_build_config._write_cloud_config(output_file.strpath)
        yaml.load(output_file.read())

    def test_written_output_is_cloud_config(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        generate_build_config._write_cloud_config(output_file.strpath)
        assert '#cloud-config' == output_file.readlines(cr=False)[0].strip()

    def test_default_build_id_is_output(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        generate_build_config._write_cloud_config(output_file.strpath)
        assert '- export BUILD_ID=output\n' in output_file.readlines()

    def test_write_files_not_included_by_default(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        generate_build_config._write_cloud_config(output_file.strpath)
        cloud_config = yaml.load(output_file.open())
        assert 'write_files' not in cloud_config


class TestWriteCloudConfigWithCustomisationScript(object):

    @pytest.fixture(params=('customisation_script',
                            'binary_customisation_script'))
    def customisation_script_kwargs(self, request):
        return {request.param: self.script.strpath}

    @pytest.fixture(autouse=True)
    def customisation_script_tmpdir(self, tmpdir):
        self.output_file = tmpdir.join('output.yaml')
        self.script = tmpdir.join('custom_script.sh')
        self.content = '#!/bin/sh\ntrue'
        self.script.write(self.content)

    def test_single_write_files_stanza_produced_for_customisation_script(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert 1 == len(cloud_config['write_files'])

    def test_customisation_script_owned_by_root(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert 'root:root' == cloud_config['write_files'][0]['owner']

    def test_customisation_script_is_executable_by_root(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert '7' == cloud_config['write_files'][0]['permissions'][1]

    def test_customisation_script_placed_in_correct_directory(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        path = py.path.local(cloud_config['write_files'][0]['path'])
        assert ('/home/ubuntu/build-output/chroot-autobuild'
                '/usr/share/livecd-rootfs/live-build/ubuntu-cpc/hooks' ==
                path.dirname)

    def test_customisation_script_is_an_appropriate_hook(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        path = py.path.local(cloud_config['write_files'][0]['path'])
        if 'customisation_script' in customisation_script_kwargs:
            assert '.chroot' == path.ext
        else:
            assert '.binary' == path.ext

    def test_customisation_script_marked_as_base64(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert 'b64' == cloud_config['write_files'][0]['encoding']

    def test_customisation_script_is_included_in_template_as_base64(
            self, customisation_script_kwargs):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert self.content == base64.b64decode(
            cloud_config['write_files'][0]['content']).decode('utf-8')

    def test_empty_customisation_script_doesnt_produce_write_files_stanza(
            self, customisation_script_kwargs):
        self.script.remove()
        self.script.ensure()
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **customisation_script_kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert 'write_files' not in cloud_config


class TestMain(object):

    def test_main_exits_nonzero_with_no_cli_arguments(self, mocker):
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py'])
        with pytest.raises(SystemExit) as excinfo:
            generate_build_config.main()
        assert excinfo.value.code > 0

    def test_main_exits_nonzero_with_too_many_cli_arguments(self, mocker):
        mocker.patch(
            'sys.argv', ['ubuntu-standalone-builder.py', '1', '2', '3'])
        with pytest.raises(SystemExit) as excinfo:
            generate_build_config.main()
        assert excinfo.value.code > 0

    def test_main_passes_first_argument_to_write_cloud_config(self, mocker):
        output_filename = 'output.yaml'
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py',
                                  output_filename])
        write_cloud_config_mock = mocker.patch(
            'generate_build_config._write_cloud_config')
        generate_build_config.main()
        assert [mocker.call(
            output_filename, customisation_script=None, ppa=None)] == \
            write_cloud_config_mock.call_args_list

    def test_main_passes_customisation_script(self, mocker):
        customisation_script = 'script.sh'
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py',
                                  'output.yaml', '--customisation-script',
                                  customisation_script])
        write_cloud_config_mock = mocker.patch(
            'generate_build_config._write_cloud_config')
        generate_build_config.main()
        assert [mocker.call(mocker.ANY,
                            customisation_script=customisation_script,
                            ppa=None)] == \
            write_cloud_config_mock.call_args_list
