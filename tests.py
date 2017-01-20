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
