# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import logging
import sys
from unittest.mock import patch, call, ANY
import tempfile
import os
import pickle
import shutil

from controller.scan import RemoteScanner
from ssh import SshcpError
from common import AppError
from common import Localization


class TestRemoteScanner(unittest.TestCase):
    temp_dir = None
    temp_scan_script = None

    def setUp(self):
        ssh_patcher = patch('controller.scan.remote_scanner.Sshcp')
        self.addCleanup(ssh_patcher.stop)
        self.mock_ssh_cls = ssh_patcher.start()
        self.mock_ssh = self.mock_ssh_cls.return_value

        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        # Ssh to return mangled binary by default
        self.mock_ssh.shell.return_value = b'error'

    @classmethod
    def setUpClass(cls):
        TestRemoteScanner.temp_dir = tempfile.mkdtemp(prefix="test_remote_scanner")
        TestRemoteScanner.temp_scan_script = os.path.join(TestRemoteScanner.temp_dir, "script")
        with open(TestRemoteScanner.temp_scan_script, "w") as f:
            f.write("")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TestRemoteScanner.temp_dir)

    def test_correctly_initializes_ssh(self):
        self.ssh_args = {}

        def mock_ssh_ctor(**kwargs):
            self.ssh_args = kwargs

        self.mock_ssh_cls.side_effect = mock_ssh_ctor

        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.assertIsNotNone(scanner)
        self.assertEqual("my remote address", self.ssh_args["host"])
        self.assertEqual(1234, self.ssh_args["port"])
        self.assertEqual("my remote user", self.ssh_args["user"])
        self.assertEqual("my password", self.ssh_args["password"])

    def test_installs_scan_script_on_first_scan(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh returns error for md5sum check, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                raise SshcpError("an ssh error")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )
        self.mock_ssh.copy.reset_mock()

        # should not be called the second time
        scanner.scan()
        self.mock_ssh.copy.assert_not_called()

    def test_appends_script_name_to_remote_path(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan"
        )

        self.ssh_run_command_count = 0

        # Ssh returns error for md5sum check, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                raise SshcpError("an ssh error")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        # check for appended path ('script')
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )

    def test_calls_correct_ssh_md5sum_command(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh returns error for md5sum check, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                raise SshcpError("an ssh error")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.assertEqual(2, self.mock_ssh.shell.call_count)
        self.mock_ssh.shell.assert_has_calls([
            call("echo 'd41d8cd98f00b204e9800998ecf8427e /remote/path/to/scan/script' | md5sum -c --quiet"),
            call(ANY)
        ])

    def test_skips_install_on_md5sum_match(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh returns empty on md5sum, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                return b''
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.mock_ssh.copy.assert_not_called()
        self.mock_ssh.copy.reset_mock()

        # should not be called the second time either
        scanner.scan()
        self.mock_ssh.copy.assert_not_called()

    def test_installs_scan_script_on_any_md5sum_output(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh returns error for md5sum check, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                return b'some output from md5sum'
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )
        self.mock_ssh.copy.reset_mock()

    def test_installs_scan_script_on_md5sum_error(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh returns error for md5sum check, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                raise SshcpError("an ssh error")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )
        self.mock_ssh.copy.reset_mock()

    def test_calls_correct_ssh_scan_command(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh returns error for md5sum check, empty pickle dump for later commands
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # first try
                raise SshcpError("an ssh error")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.assertEqual(2, self.mock_ssh.shell.call_count)
        self.mock_ssh.shell.assert_called_with(
            "'/remote/path/to/scan/script' '/remote/path/to/scan'"
        )

    def test_raises_app_error_on_failed_ssh(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh run command raises error the first time, succeeds the second time
        # noinspection PyUnusedLocal
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # md5sum check
                return b''
            elif self.ssh_run_command_count == 2:
                # first try
                raise SshcpError("an ssh error")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        with self.assertRaises(AppError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_SCAN, str(ctx.exception))

    def test_raises_app_error_on_failed_copy(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        # noinspection PyUnusedLocal
        def ssh_copy(*args, **kwargs):
            raise SshcpError("an scp error")
        self.mock_ssh.copy.side_effect = ssh_copy

        with self.assertRaises(AppError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_INSTALL, str(ctx.exception))

    def test_suppresses_and_retries_on_ssh_error_text_file_busy(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh run command raises error the first time, succeeds the second time
        # noinspection PyUnusedLocal
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # md5sum check
                return b''
            elif self.ssh_run_command_count == 2:
                # first try
                raise SshcpError("bash: /remote/path/to/scan: Text file busy")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.assertEqual(3, self.mock_ssh.shell.call_count)

    def test_fails_after_max_retries_on_suppressed_error(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        # noinspection PyUnusedLocal
        def ssh_shell(*args):
                raise SshcpError("bash: /remote/path/to/scan: Text file busy")
        self.mock_ssh.shell.side_effect = ssh_shell

        with self.assertRaises(AppError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_SCAN, str(ctx.exception))
        # 7 tries: md5sum check + initial try + 5 retries
        self.assertEqual(7, self.mock_ssh.shell.call_count)

    def test_suppresses_and_retries_on_ssh_error_exchange_identification(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh run command raises error the first time, succeeds the second time
        # noinspection PyUnusedLocal
        def ssh_run_command(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count < 2:
                raise SshcpError("ssh_exchange_identification: read: Connection reset by peer")
            else:
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_run_command

        scanner.scan()
        self.assertEqual(2, self.mock_ssh.shell.call_count)

    def test_suppresses_and_retries_on_ssh_error_cannot_create_temp_dir(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh run command raises error the first time, succeeds the second time
        # noinspection PyUnusedLocal
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # md5sum check
                return b''
            elif self.ssh_run_command_count == 2:
                # first try
                raise SshcpError("[23033] INTERNAL ERROR: cannot create temporary directory!")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.assertEqual(3, self.mock_ssh.shell.call_count)

    def test_suppresses_and_retries_on_ssh_error_connection_timed_out(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.ssh_run_command_count = 0

        # Ssh run command raises error the first time, succeeds the second time
        # noinspection PyUnusedLocal
        def ssh_shell(*args):
            self.ssh_run_command_count += 1
            if self.ssh_run_command_count == 1:
                # md5sum check
                return b''
            elif self.ssh_run_command_count == 2:
                # first try
                raise SshcpError("connect to host host.remote.com port 2202: Connection timed out")
            else:
                # later tries
                return pickle.dumps([])
        self.mock_ssh.shell.side_effect = ssh_shell

        scanner.scan()
        self.assertEqual(3, self.mock_ssh.shell.call_count)

    def test_raises_app_error_on_mangled_output(self):
        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        def ssh_shell(*args):
            return "mangled data".encode()
        self.mock_ssh.shell.side_effect = ssh_shell

        with self.assertRaises(AppError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_SCAN, str(ctx.exception))
