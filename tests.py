import pytest
import yaml

import ubuntu_standalone_builder


class TestWriteCloudConfig(object):

    def test_writes_to_file(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        ubuntu_standalone_builder._write_cloud_config(output_file.strpath)
        assert output_file.check()

    def test_written_output_is_yaml(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        ubuntu_standalone_builder._write_cloud_config(output_file.strpath)
        yaml.load(output_file.read())

    def test_written_output_is_cloud_config(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        ubuntu_standalone_builder._write_cloud_config(output_file.strpath)
        assert '#cloud-config' == output_file.readlines(cr=False)[0].strip()

    def test_default_build_id_is_output(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        ubuntu_standalone_builder._write_cloud_config(output_file.strpath)
        assert '- export BUILD_ID=output\n' in output_file.readlines()


class TestMain(object):

    def test_main_exits_nonzero_with_no_cli_arguments(self, mocker):
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py'])
        with pytest.raises(SystemExit) as excinfo:
            ubuntu_standalone_builder.main()
        assert excinfo.value.code > 0

    def test_main_exits_nonzero_with_too_many_cli_arguments(self, mocker):
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py', '1', '2'])
        with pytest.raises(SystemExit) as excinfo:
            ubuntu_standalone_builder.main()
        assert excinfo.value.code > 0

    def test_main_passes_first_argument_to_write_cloud_config(self, mocker):
        output_filename = 'output.yaml'
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py',
                                  output_filename])
        write_cloud_config_mock = mocker.patch(
            'ubuntu_standalone_builder._write_cloud_config')
        ubuntu_standalone_builder.main()
        assert [mocker.call(output_filename)] == write_cloud_config_mock.call_args_list
