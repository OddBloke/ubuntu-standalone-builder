import ubuntu_standalone_builder


class TestWriteCloudConfig(object):

    def test_writes_to_file(self, tmpdir):
        output_file = tmpdir.join('output.yaml')
        ubuntu_standalone_builder._write_cloud_config(output_file.strpath)
        assert output_file.check()
