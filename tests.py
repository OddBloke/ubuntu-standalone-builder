import base64

import py
import pytest
import yaml
from six.moves.urllib.parse import urlparse

import generate_build_config


class TestGetPPASnippet(object):

    def test_unknown_url(self):
        with pytest.raises(ValueError):
            generate_build_config._get_ppa_snippet('ftp://blah')

    def test_public_ppa(self):
        result = generate_build_config._get_ppa_snippet('ppa:foo/bar')
        expected = '- chroot $CHROOT_ROOT add-apt-repository -y -u ppa:foo/bar'
        assert result == expected

    def test_https_not_private_ppa(self):
        with pytest.raises(ValueError):
            generate_build_config._get_ppa_snippet('https://blah')

    def test_private_ppa_no_key(self):
        with pytest.raises(ValueError):
            generate_build_config._get_ppa_snippet(
                'https://private-ppa.example.com')

    def test_private_ppa_with_key(self):
        result = generate_build_config._get_ppa_snippet(
            'https://private-ppa.example.com', 'DEADBEEF')
        assert 'apt-get install -y apt-transport-https' in result
        assert 'deb https://private-ppa.example.com xenial main' in result
        assert ('apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 '
                '--recv-keys DEADBEEF' in result)


@pytest.fixture
def write_cloud_config_to_tmpfile(tmpdir):
    def _write_cloud_config_to_tmpfile(*args, **kwargs):
        output_file = tmpdir.join('output.yaml')
        generate_build_config._write_cloud_config(
            output_file.strpath, *args, **kwargs)
        return output_file
    return _write_cloud_config_to_tmpfile


class TestWriteCloudConfig(object):

    def test_writes_to_file(self, write_cloud_config_to_tmpfile):
        assert write_cloud_config_to_tmpfile().check()

    def test_written_output_is_yaml(self, write_cloud_config_to_tmpfile):
        yaml.load(write_cloud_config_to_tmpfile().read())

    def test_written_output_is_cloud_config(
            self, write_cloud_config_to_tmpfile):
        assert '#cloud-config' \
            == write_cloud_config_to_tmpfile().readlines(cr=False)[0].strip()

    def test_default_build_id_is_output(self, write_cloud_config_to_tmpfile):
        assert '- export BUILD_ID=output\n' in \
            write_cloud_config_to_tmpfile().readlines()

    def test_write_files_not_included_by_default(
            self, write_cloud_config_to_tmpfile):
        cloud_config = yaml.load(write_cloud_config_to_tmpfile().open())
        assert 'write_files' not in cloud_config

    def test_no_ppa_included_by_default(self, write_cloud_config_to_tmpfile):
        content = write_cloud_config_to_tmpfile().read()
        assert 'add-apt-repository' not in content
        assert 'apt-transport-https' not in content

    def _get_wget_line(self, output_file):
        wget_lines = [ln for ln in output_file.readlines() if 'wget' in ln]
        assert 1 == len(wget_lines)
        return wget_lines[0]

    def test_daily_image_used(self, write_cloud_config_to_tmpfile):
        wget_line = self._get_wget_line(write_cloud_config_to_tmpfile())
        assert 'xenial-server-cloudimg-amd64-root.tar.xz ' in wget_line

    def test_latest_daily_image_used(self, write_cloud_config_to_tmpfile):
        url = self._get_wget_line(write_cloud_config_to_tmpfile()).split()[2]
        path = urlparse(url).path
        assert 'current' == path.split('/')[2]

    def test_ppa_snippet_included(self, write_cloud_config_to_tmpfile):
        output_file = write_cloud_config_to_tmpfile(ppa='ppa:foo/bar')
        assert 'add-apt-repository -y -u ppa:foo/bar' in output_file.read()

    def test_binary_hook_filter_included(self, write_cloud_config_to_tmpfile):
        hook_filter = 'some*glob*'
        output_file = write_cloud_config_to_tmpfile(
            binary_hook_filter=hook_filter)
        cloud_config = yaml.load(output_file.open())
        for stanza in cloud_config['write_files']:
            content = base64.b64decode(stanza['content']).decode('utf-8')
            if '{}|9997*|9998*|9999*'.format(hook_filter) in content:
                break
        else:
            pytest.fail('Binary hook filter not correctly included.')


def customisation_script_combinations():
    customisation_script_content = '#!/bin/sh\n-- chroot --'
    binary_customisation_script_content = '#!/bin/sh\n-- binary --'
    return [
        {'customisation_script': customisation_script_content},
        {'binary_customisation_script': binary_customisation_script_content},
        {'customisation_script': customisation_script_content,
         'binary_customisation_script': binary_customisation_script_content},
    ]


class TestWriteCloudConfigWithCustomisationScript(object):

    @pytest.fixture(autouse=True, params=customisation_script_combinations())
    def customisation_script_tmpdir(self, request, tmpdir, monkeypatch):
        self.output_file = tmpdir.join('output.yaml')
        self.kwargs = {}
        self.test_config = {}
        for script in request.param:
            script_file = tmpdir.join(script + '.sh')
            script_file.write(request.param[script])
            self.kwargs[script] = script_file.strpath
            self.test_config[script] = {'script_file': script_file,
                                        'content': request.param[script]}
        self.setup_content = '#!/bin/sh\n-- setup --'
        monkeypatch.setattr(
            generate_build_config, "SETUP_CONTENT", self.setup_content)
        self.teardown_content = '#!/bin/sh\n-- teardown --'
        monkeypatch.setattr(
            generate_build_config, "TEARDOWN_CONTENT", self.teardown_content)

    def test_write_files_stanza_count_produced_for_customisation_script(self):
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        expected_count = 0
        if 'customisation_script' in self.kwargs:
            expected_count += 3
        if 'binary_customisation_script' in self.kwargs:
            expected_count += 1
        assert expected_count == len(cloud_config['write_files'])

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
            content = base64.b64decode(stanza['content']).decode('utf-8')
            if ('-- chroot --' in content or '-- setup --' in content
                    or '-- teardown --' in content):
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
            if stanza['path'].endswith('9998-local-modifications.chroot'):
                expected_content = self.test_config[
                    'customisation_script']['content']
            elif stanza['path'].endswith('binary'):
                expected_content = self.test_config[
                    'binary_customisation_script']['content']
            else:
                continue
            assert expected_content == base64.b64decode(
                stanza['content']).decode('utf-8')

    def test_empty_customisation_script_doesnt_produce_write_files_stanza(
            self):
        for test_config in self.test_config.values():
            test_config['script_file'].remove()
            test_config['script_file'].ensure()
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        assert 'write_files' not in cloud_config

    def test_setup_teardown_sequence_numbers(self):
        if list(self.kwargs.keys()) == ['binary_customisation_script']:
            pytest.skip('Test only applies to chroot hooks.')
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        sequence_numbers = {}
        for stanza in cloud_config['write_files']:
            sequence_number = stanza['path'].rsplit('/')[-1].split('-')[0]
            content = base64.b64decode(stanza['content']).decode('utf-8')
            if '-- chroot --' in content:
                sequence_numbers['chroot'] = sequence_number
            elif '-- setup --' in content:
                sequence_numbers['setup'] = sequence_number
            elif '-- teardown --' in content:
                sequence_numbers['teardown'] = sequence_number
        assert sequence_numbers['setup'] < sequence_numbers['chroot']
        assert sequence_numbers['chroot'] < sequence_numbers['teardown']

    @pytest.mark.parametrize('hook', ['setup', 'teardown'])
    def test_setup_teardown_content_matches_template(self, hook, monkeypatch):
        if list(self.kwargs.keys()) == ['binary_customisation_script']:
            pytest.skip('Test only applies to chroot hooks.')
        expected_string = '#!/bin/sh\n-- specific test content --'
        monkeypatch.setattr(
            generate_build_config,
            "{}_CONTENT".format(hook.upper()), expected_string)
        generate_build_config._write_cloud_config(
            self.output_file.strpath, **self.kwargs)
        cloud_config = yaml.load(self.output_file.open())
        contents = [base64.b64decode(stanza['content'])
                    for stanza in cloud_config['write_files']]
        expected_bytes = expected_string.encode('utf-8')
        assert expected_bytes in contents
        assert 1 == len(
            [content for content in contents if expected_bytes == content])


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

    def test_main_passes_arguments_to_write_cloud_config(self, mocker):
        output_filename = 'output.yaml'
        binary_customisation_script = 'binary.sh'
        customisation_script = 'script.sh'
        ppa = 'ppa:foo/bar'
        ppa_key = 'DEADBEEF'
        mocker.patch('sys.argv', ['ubuntu-standalone-builder.py',
                                  output_filename,
                                  '--binary-customisation-script',
                                  binary_customisation_script,
                                  '--customisation-script',
                                  customisation_script, '--ppa', ppa,
                                  '--ppa-key', ppa_key])
        write_cloud_config_mock = mocker.patch(
            'generate_build_config._write_cloud_config')
        generate_build_config.main()
        assert [mocker.call(
            output_filename,
            binary_customisation_script=binary_customisation_script,
            customisation_script=customisation_script,
            ppa=ppa,
            ppa_key=ppa_key)] == write_cloud_config_mock.call_args_list
