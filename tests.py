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


def customisation_script_combinations():
    customisation_script_content = '#!/bin/sh\nchroot'
    binary_customisation_script_content = '#!/bin/sh\nbinary'
    return [
        {'customisation_script': customisation_script_content},
        {'binary_customisation_script': binary_customisation_script_content},
    ]


class TestWriteCloudConfigWithCustomisationScript(object):

    @pytest.fixture(autouse=True, params=customisation_script_combinations())
    def customisation_script_tmpdir(self, request, tmpdir):
        self.output_file = tmpdir.join('output.yaml')
        self.kwargs = {}
        self.test_config = {}
        for script in request.param:
            script_file = tmpdir.join(script + '.sh')
            script_file.write(request.param[script])
            self.kwargs[script] = script_file.strpath
            self.test_config[script] = {'script_file': script_file,
                                        'content': request.param[script]}

    def test_single_write_files_stanza_produced_for_customisation_script(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert len(self.kwargs) == len(cloud_config['write_files'])

    def test_customisation_script_owned_by_root(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        for stanza in cloud_config['write_files']:
            assert 'root:root' == stanza['owner']

    def test_customisation_script_is_executable_by_root(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        for stanza in cloud_config['write_files']:
            assert '7' == stanza['permissions'][1]

    def test_customisation_script_placed_in_correct_directory(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        for stanza in cloud_config['write_files']:
            path = py.path.local(stanza['path'])
            assert ('/home/ubuntu/build-output/chroot-autobuild'
                    '/usr/share/livecd-rootfs/live-build/ubuntu-cpc/hooks' ==
                    path.dirname)

    def test_customisation_script_is_an_appropriate_hook(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        for stanza in cloud_config['write_files']:
            path = py.path.local(stanza['path'])
            if 'chroot' in base64.b64decode(stanza['content']).decode('utf-8'):
                assert '.chroot' == path.ext
            else:
                assert '.binary' == path.ext

    def test_customisation_script_marked_as_base64(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        for stanza in cloud_config['write_files']:
            assert 'b64' == stanza['encoding']

    def test_customisation_script_is_included_in_template_as_base64(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        for stanza in cloud_config['write_files']:
            if stanza['path'].endswith('chroot'):
                expected_content = self.test_config[
                    'customisation_script']['content']
            else:
                expected_content = self.test_config[
                    'binary_customisation_script']['content']
            assert expected_content == base64.b64decode(
                stanza['content']).decode('utf-8')

    def test_empty_customisation_script_doesnt_produce_write_files_stanza(self):
        for test_config in self.test_config.values():
            test_config['script_file'].remove()
            test_config['script_file'].ensure()
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
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
