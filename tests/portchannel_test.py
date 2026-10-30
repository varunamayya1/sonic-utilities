import os
import re
import pytest
import subprocess
import traceback
import mock

from click.testing import CliRunner
from jsonpatch import JsonPatchConflict

import config.main as config
import config.validated_config_db_connector as validated_config_db_connector
import show.main as show
import clear.main as clear
from utilities_common.db import Db
from mock import patch

EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_NO_MEMBERS_OUTPUT = """\
--------------------------------------------------------------------------
LAG: PortChannel0004 is up, mode LACP
Minimum number of links to bring PortChannel up is 1
address is 52:54:00:f2:e1:23
Fallback: Disabled
Fast_rate: Disabled
Retry_count_feature: Enabled
Retry_count: 3
MTU: 9100
LACP: mode ACTIVE, priority 65535, address 52:54:00:f2:e1:23
LAG MEMBER: None
--------------------------------------------------------------------------
"""

EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_DESELECTED_MEMBER_OUTPUT = """\
--------------------------------------------------------------------------
LAG: PortChannel0001 is down, mode LACP
Minimum number of links to bring PortChannel up is 1
address is 52:54:00:f2:e1:23
Fallback: Disabled
Fast_rate: Disabled
Retry_count_feature: Enabled
Retry_count: 3
MTU: 9100
LACP: mode ACTIVE, priority 65535, address 52:54:00:f2:e1:23
LAG MEMBER: Ethernet112(deselected)
    LACP Actor: port 113, address 52:54:00:f2:e1:23, key 11
    LACP Actor State: (Act, Agg, Def)
    LACP Partner: port 0, address 00:00:00:00:00:00, key 0
    LACP Partner State: (Tmo)
    Statistics:
        lacpdu_illegal_pkts: 0
        lacpdu_rx_stats: 0
        lacpdu_tx_stats: 1103
        last rx lacpdu at: N/A
        last tx lacpdu at: 2025-06-26T07:54:23.926776098Z
--------------------------------------------------------------------------
"""

EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_SELECTED_MEMBER_OUTPUT = """\
--------------------------------------------------------------------------
LAG: PortChannel0002 is up, mode LACP
Minimum number of links to bring PortChannel up is 1
address is 52:54:00:f2:e1:23
Fallback: Disabled
Fast_rate: Disabled
Retry_count_feature: Enabled
Retry_count: 3
MTU: 9100
LACP: mode ACTIVE, priority 65535, address 52:54:00:f2:e1:23
LAG MEMBER: Ethernet116(selected)
    LACP Actor: port 117, address 52:54:00:f2:e1:23, key 12
    LACP Actor State: (Act, Agg, Sync, Coll, Dist)
    LACP Partner: port 1, address 1e:af:77:fc:79:ee, key 13
    LACP Partner State: (Act, Agg, Sync, Coll, Dist)
    Statistics:
        lacpdu_illegal_pkts: 0
        lacpdu_rx_stats: 1003
        lacpdu_tx_stats: 1103
        last rx lacpdu at: 2025-06-26T07:54:23.926776098Z
        last tx lacpdu at: 2025-06-26T07:54:23.926776098Z
--------------------------------------------------------------------------
"""

class TestPortChannel(object):

    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    @patch("config.main.is_portchannel_present_in_db", mock.Mock(return_value=False))
    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=ValueError))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_add_portchannel_with_invalid_name_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_portchannel_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>' " \
            "and its length should not exceed 15 characters" in result.output

        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChanl00000"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChanl00000 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>' and " \
            "its length should not exceed 15 characters" in result.output

    @patch("config.validated_config_db_connector.ValidatedConfigDBConnector.validated_set_entry", mock.Mock(side_effect=JsonPatchConflict))
    @patch("validated_config_db_connector.device_info.is_yang_config_validation_enabled", mock.Mock(return_value=True))
    def test_delete_nonexistent_portchannel_yang_validation(self):
        config.ADHOC_VALIDATION = False
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "PortChan005 is not present" in result.output

    def test_delete_portchannel_with_invalid_name_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel with invalid name
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChan005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_delete_portchannel_in_use_by_dhcpv4_relay(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel10"], obj=obj)

        # Enable has_sonic_dhcpv4_relay flag
        db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {"has_sonic_dhcpv4_relay": "True"})

        db.cfgdb.set_entry("DHCPV4_RELAY", "Vlan100", {"source_interface": "PortChannel10"})

        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel10"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Interface 'PortChannel10' is in use by Vlan100" in result.output

        db.cfgdb.set_entry("DHCPV4_RELAY", "Vlan100", None)

    def test_add_existing_portchannel_again(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel which is already created
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0001 already exists!" in result.output

    def test_delete_non_existing_portchannel_adhoc_validation(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel which is not present
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel0005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    @pytest.mark.parametrize("fast_rate", ["False", "True", "false", "true"])
    def test_add_portchannel_with_fast_rate_adhoc_validation(self, fast_rate):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with fats rate
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0005", "--fast-rate", fast_rate], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @pytest.mark.parametrize("fast_rate", ["Fls", "tru"])
    def test_add_portchannel_with_invalid_fast_rate(self, fast_rate):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel with invalid fats rate
        result = runner.invoke(config.config.commands["portchannel"].commands["add"], ["PortChannel0005", "--fast-rate", fast_rate], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Invalid value for \'--fast-rate\'' in result.output

    @pytest.mark.parametrize("lacp_mode", ["active", "passive", "Active", "PASSIVE"])
    def test_add_portchannel_with_lacp_mode_adhoc_validation(self, lacp_mode):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               ["PortChannel0006", "--lacp-mode", lacp_mode], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        expected_active = 'true' if lacp_mode.lower() == 'active' else 'false'
        entry = db.cfgdb.get_entry('PORTCHANNEL', 'PortChannel0006')
        assert entry.get('active') == expected_active

    @pytest.mark.parametrize("lacp_mode", ["auto", "static"])
    def test_add_portchannel_with_invalid_lacp_mode(self, lacp_mode):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               ["PortChannel0006", "--lacp-mode", lacp_mode], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Invalid value for \'--lacp-mode\'' in result.output

    def _add_portchannel(self, runner, obj, name, *options):
        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               [name, *options], obj=obj)
        assert result.exit_code == 0, result.output

    def _invoke(self, runner, obj, command, args):
        return runner.invoke(config.config.commands["portchannel"].commands[command], args, obj=obj)

    def _entry(self, db, name):
        return db.cfgdb.get_entry('PORTCHANNEL', name)

    def test_portchannel_lacp_mode_default_active(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0007")
        assert self._entry(db, "PortChannel0007")['active'] == 'true'

    def test_set_portchannel_lacp_mode_passive(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0008")

        result = self._invoke(runner, obj, "lacp-mode", ["PortChannel0008", "passive"])
        assert result.exit_code == 0, result.output
        assert self._entry(db, "PortChannel0008")['active'] == 'false'

        result = self._invoke(runner, obj, "lacp-mode", ["PortChannel0008", "ACTIVE"])
        assert result.exit_code == 0, result.output
        assert self._entry(db, "PortChannel0008")['active'] == 'true'

    def test_set_portchannel_invalid_lacp_mode(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0008")

        result = self._invoke(runner, obj, "lacp-mode", ["PortChannel0008", "static"])
        assert result.exit_code != 0
        assert "Invalid value for '<lacp_mode>'" in result.output

    def test_set_non_existing_portchannel_lacp_mode(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = self._invoke(runner, obj, "lacp-mode", ["PortChannel0009", "passive"])
        assert result.exit_code != 0
        assert "Error: PortChannel0009 is not present." in result.output

    def test_set_portchannel_min_links(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0020")
        assert self._entry(db, "PortChannel0020")['min_links'] == '1'

        result = self._invoke(runner, obj, "min-links", ["PortChannel0020", "3"])
        assert result.exit_code == 0, result.output
        assert self._entry(db, "PortChannel0020")['min_links'] == '3'

    @pytest.mark.parametrize("min_links", ["0", "1025", "abc"])
    def test_set_portchannel_invalid_min_links(self, min_links):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0020")

        result = self._invoke(runner, obj, "min-links", ["PortChannel0020", min_links])
        assert result.exit_code != 0
        assert "Invalid value for '<min_links>'" in result.output

    def test_set_portchannel_fallback_defaults_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0021")
        assert 'fallback' not in self._entry(db, "PortChannel0021")

        result = self._invoke(runner, obj, "fallback", ["PortChannel0021", "true"])
        assert result.exit_code == 0, result.output
        entry = self._entry(db, "PortChannel0021")
        assert entry['fallback'] == 'true'
        assert entry['fallback_timeout'] == '90'

    def test_set_portchannel_fallback_with_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0022")

        result = self._invoke(runner, obj, "fallback",
                              ["PortChannel0022", "TRUE", "--fallback-timeout", "30"])
        assert result.exit_code == 0, result.output
        entry = self._entry(db, "PortChannel0022")
        assert entry['fallback'] == 'true'
        assert entry['fallback_timeout'] == '30'

    def test_portchannel_fallback_toggle_preserves_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0023",
                              "--fallback", "true", "--fallback-timeout", "45")

        result = self._invoke(runner, obj, "fallback", ["PortChannel0023", "false"])
        assert result.exit_code == 0, result.output
        entry = self._entry(db, "PortChannel0023")
        assert entry['fallback'] == 'false'
        assert entry['fallback_timeout'] == '45'

        result = self._invoke(runner, obj, "fallback", ["PortChannel0023", "true"])
        assert result.exit_code == 0, result.output
        entry = self._entry(db, "PortChannel0023")
        assert entry['fallback'] == 'true'
        assert entry['fallback_timeout'] == '45'

    def test_set_portchannel_fallback_false_rejects_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0024", "--fallback", "true")

        result = self._invoke(runner, obj, "fallback",
                              ["PortChannel0024", "false", "--fallback-timeout", "30"])
        assert result.exit_code != 0
        assert "--fallback-timeout can only be used when enabling fallback" in result.output
        assert self._entry(db, "PortChannel0024")['fallback'] == 'true'

    def test_set_portchannel_fallback_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0025", "--fallback", "true")
        assert self._entry(db, "PortChannel0025")['fallback_timeout'] == '90'

        result = self._invoke(runner, obj, "fallback-timeout", ["PortChannel0025", "120"])
        assert result.exit_code == 0, result.output
        assert result.output == ""
        assert self._entry(db, "PortChannel0025")['fallback_timeout'] == '120'

    def test_set_portchannel_fallback_timeout_while_fallback_disabled(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0026", "--fallback", "true")
        result = self._invoke(runner, obj, "fallback", ["PortChannel0026", "false"])
        assert result.exit_code == 0, result.output

        result = self._invoke(runner, obj, "fallback-timeout", ["PortChannel0026", "60"])
        assert result.exit_code == 0, result.output
        assert "takes effect when fallback is enabled" in result.output
        assert self._entry(db, "PortChannel0026")['fallback_timeout'] == '60'

    def test_set_portchannel_fallback_timeout_without_fallback(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0027")

        result = self._invoke(runner, obj, "fallback-timeout", ["PortChannel0027", "60"])
        assert result.exit_code != 0
        assert "Fallback is not configured on PortChannel0027" in result.output
        assert "config portchannel fallback PortChannel0027 true --fallback-timeout 60" in result.output
        assert 'fallback_timeout' not in self._entry(db, "PortChannel0027")

    @pytest.mark.parametrize("fallback_timeout", ["0", "65536", "abc"])
    def test_set_portchannel_invalid_fallback_timeout(self, fallback_timeout):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0025", "--fallback", "true")

        result = self._invoke(runner, obj, "fallback-timeout", ["PortChannel0025", fallback_timeout])
        assert result.exit_code != 0
        assert "Invalid value for '<1-65535>'" in result.output

    def test_set_portchannel_fast_rate(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}
        self._add_portchannel(runner, obj, "PortChannel0028")
        assert self._entry(db, "PortChannel0028")['fast_rate'] == 'false'

        result = self._invoke(runner, obj, "fast-rate", ["PortChannel0028", "True"])
        assert result.exit_code == 0, result.output
        assert self._entry(db, "PortChannel0028")['fast_rate'] == 'true'

    @pytest.mark.parametrize("command,value", [("lacp-mode", "passive"),
                                               ("min-links", "2"),
                                               ("fallback", "true"),
                                               ("fallback-timeout", "60"),
                                               ("fast-rate", "true")])
    def test_set_runtime_option_on_non_existing_portchannel(self, command, value):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = self._invoke(runner, obj, command, ["PortChannel0029", value])
        assert result.exit_code != 0
        assert "Error: PortChannel0029 is not present." in result.output
        assert not self._entry(db, "PortChannel0029")

    @pytest.mark.parametrize("command,headers,values", [
        ("lacp-mode", ["LACP Mode"], ["active"]),
        ("min-links", ["Min Links"], ["1"]),
        ("fallback", ["Fallback", "Fallback Timeout"], ["false", "90"]),
        ("fast-rate", ["Fast Rate"], ["false"])])
    def test_show_portchannel_runtime_option(self, command, headers, values):
        runner = CliRunner()
        db = Db()
        show_cmd = show.cli.commands["interfaces"].commands["portchannel"].commands[command]

        result = runner.invoke(show_cmd, [], obj=db)
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        assert re.split(r'\s{2,}', lines[0].strip()) == ['PortChannel'] + headers
        rows = {line.split()[0]: line.split()[1:] for line in lines[2:]}
        assert rows == {"PortChannel0001": values, "PortChannel0002": values,
                        "PortChannel0003": values, "PortChannel0004": values,
                        "PortChannel1001": ["N/A"] * len(values)}

        result = runner.invoke(show_cmd, ["PortChannel0002"], obj=db)
        assert result.exit_code == 0, result.output
        assert [line.split()[0] for line in result.output.splitlines()[2:]] == ["PortChannel0002"]

    @pytest.mark.parametrize("command", ["lacp-mode", "min-links", "fallback", "fast-rate"])
    def test_show_portchannel_runtime_option_non_existing(self, command):
        runner = CliRunner()
        db = Db()
        show_cmd = show.cli.commands["interfaces"].commands["portchannel"].commands[command]

        result = runner.invoke(show_cmd, ["PortChannel0029"], obj=db)
        assert result.exit_code != 0
        assert "No such PortChannel interface: PortChannel0029" in result.output

    def test_add_portchannel_with_fallback_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               ["PortChannel0005", "--fallback", "true",
                                "--fallback-timeout", "120"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        entry = db.cfgdb.get_entry('PORTCHANNEL', 'PortChannel0005')
        assert entry['fallback'] == 'true'
        assert entry['fallback_timeout'] == '120'

    def test_add_portchannel_fallback_defaults_timeout(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        # fallback without an explicit timeout adopts the 90s default
        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               ["PortChannel0005", "--fallback", "true"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        entry = db.cfgdb.get_entry('PORTCHANNEL', 'PortChannel0005')
        assert entry['fallback'] == 'true'
        assert entry['fallback_timeout'] == '90'

    def test_add_portchannel_fallback_timeout_without_fallback(self):
        config.ADHOC_VALIDATION = True
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               ["PortChannel0005", "--fallback-timeout", "120"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "--fallback-timeout requires --fallback to be enabled" in result.output

    @pytest.mark.parametrize("fallback_timeout", ["0", "65536", "abc"])
    def test_add_portchannel_with_invalid_fallback_timeout(self, fallback_timeout):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb}

        result = runner.invoke(config.config.commands["portchannel"].commands["add"],
                               ["PortChannel0005", "--fallback", "true",
                                "--fallback-timeout", fallback_timeout], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert 'Invalid value for \'--fallback-timeout\'' in result.output

    def test_add_portchannel_member_with_invalid_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChan005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_delete_portchannel_member_with_invalid_name(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChan005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChan005 is invalid!, name should have prefix 'PortChannel' and suffix '<0-9999>'" in result.output

    def test_add_non_existing_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with portchannel is not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_delete_non_existing_portchannel_member(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with portchannel is not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChannel0005", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_add_portchannel_member_which_has_ipaddress(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which has ip-address
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet0"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error:  Ethernet0 has ip address configured" in result.output

    def test_add_portchannel_member_which_has_subintf(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which has ip-address
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet36"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        print(result.output)
        assert "Error:  Ethernet36 has subinterfaces configured" in result.output

    def test_add_portchannel_member_which_is_member_of_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which is member of Vlan
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet24"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet24 Interface configured as VLAN_MEMBER under vlan : Vlan2000" in result.output

    def test_add_portchannel_member_which_is_member_of_another_po(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # add a portchannel member with port which is member of another PO
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel1001", "Ethernet116"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet116 Interface is already member of PortChannel0002 " in result.output

    def test_delete_portchannel_member_which_is_member_of_another_po(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # delete a portchannel member with port which is member of another PO
        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["del"], ["PortChannel1001", "Ethernet116"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet116 is not a member of portchannel PortChannel1001" in result.output

    def test_add_portchannel_member_with_acl_bindngs(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb, 'db_wrap':db, 'namespace':''}

        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0002", "Ethernet100"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Port Ethernet100 is already bound to following ACL_TABLES:" in result.output

    def test_add_portchannel_member_with_pbh_bindngs(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb, 'db_wrap':db, 'namespace':''}

        result = runner.invoke(config.config.commands["portchannel"].commands["member"].commands["add"], ["PortChannel0002", "Ethernet60"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Port Ethernet60 is already bound to following PBH_TABLES:" in result.output

    def test_delete_portchannel_which_is_member_of_a_vlan(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # try to delete the portchannel when its member of a vlan
        result = runner.invoke(config.config.commands["portchannel"].commands["del"], ["PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "PortChannel1001 has vlan Vlan4000 configured, remove vlan membership to proceed" in result.output

    def test_get_invalid_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # get the retry count of a portchannel with an invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["Ethernet48"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet48 is invalid!" in result.output

    def test_set_invalid_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # set the retry count of a portchannel with an invalid portchannel name
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["Ethernet48", "5"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: Ethernet48 is invalid!" in result.output

    def test_get_non_existing_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # get the retry count of a portchannel with portchannel not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel0005"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    def test_set_non_existing_portchannel_retry_count(self):
        runner = CliRunner()
        db = Db()
        obj = {'db':db.cfgdb}

        # set the retry count of a portchannel with portchannel not yet created
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel0005", "5"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Error: PortChannel0005 is not present." in result.output

    originalSubprocessPopen = subprocess.Popen

    class SubprocessMock:
        def __init__(self, *args, **kwargs):
            self.retryCountEnabled = True
            self.timeout = False

        def __call__(self, *args, **kwargs):
            stdoutResult = ""
            stderrResult = ""
            rc = 0

            commandArgs = args[0]
            if commandArgs[0] != "teamdctl":
                return TestPortChannel.originalSubprocessPopen(*args, **kwargs)
            if self.timeout:
                return TestPortChannel.originalSubprocessPopen(["sleep", "90"], **kwargs)
            # Find the runner item in the command args (handles both with and without -n flag)
            # For "get": [..., "get", "runner.xxx"] - runner item is last
            # For "set": [..., "set", "runner.retry_count", value] - runner item is second to last
            if "runner.enable_retry_count_feature" in commandArgs:
                return TestPortChannel.originalSubprocessPopen(["echo", "true" if self.retryCountEnabled else "false"], **kwargs)
            elif "runner.retry_count" in commandArgs:
                if "get" in commandArgs:
                    return TestPortChannel.originalSubprocessPopen(["echo", "3"], **kwargs)
                elif "set" in commandArgs:
                    return TestPortChannel.originalSubprocessPopen(["echo", ""], **kwargs)
                else:
                    return TestPortChannel.originalSubprocessPopen(["false"], **kwargs)
            else:
                return TestPortChannel.originalSubprocessPopen(["false"], **kwargs)

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_get_portchannel_retry_count_disabled(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'teamdctl_command': ['teamdctl']}

        subprocessMock.retryCountEnabled = False

        # get the retry count of a portchannel, but when the retry count feature is disabled
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Retry count feature is not enabled!" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_set_portchannel_retry_count_disabled(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'teamdctl_command': ['teamdctl']}

        subprocessMock.retryCountEnabled = False

        # set the retry count of a portchannel, but when the retry count feature is disabled
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel1001", "5"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Retry count feature is not enabled!" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_get_portchannel_retry_count_timeout(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'teamdctl_command': ['teamdctl']}

        subprocessMock.retryCountEnabled = True
        subprocessMock.timeout = True

        # get the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel1001"], obj=obj)
        # expect a timeout failure
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Unable to get the retry count" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_set_portchannel_retry_count_timeout(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'teamdctl_command': ['teamdctl']}

        subprocessMock.retryCountEnabled = True
        subprocessMock.timeout = True

        # set the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel1001", "5"], obj=obj)
        # expect a timeout failure
        print(result.exit_code)
        print(result.output)
        assert result.exit_code != 0
        assert "Unable to set the retry count" in result.output

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_get_portchannel_retry_count(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'teamdctl_command': ['teamdctl']}

        subprocessMock.retryCountEnabled = True

        # get the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["get"], ["PortChannel1001"], obj=obj)
        # output has been mocked
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.strip() == "3"

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_set_portchannel_retry_count(self, subprocessMock):
        runner = CliRunner()
        db = Db()
        obj = {'db': db.cfgdb, 'teamdctl_command': ['teamdctl']}

        subprocessMock.retryCountEnabled = True

        # set the retry count of a portchannel
        result = runner.invoke(config.config.commands["portchannel"].commands["retry-count"].commands["set"], ["PortChannel1001", "5"], obj=obj)
        # output has been mocked
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output == ""

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_portchannel_retry_count_group_default_namespace(self, subprocessMock):
        """Test that portchannel_retry_count group sets up teamdctl_command for default namespace"""
        runner = CliRunner()
        db = Db()
        # Don't pass teamdctl_command - let the group function set it up
        obj = {'db': db.cfgdb, 'namespace': ''}

        subprocessMock.retryCountEnabled = True

        # Invoke through retry-count group command to trigger the group callback
        result = runner.invoke(
            config.config.commands["portchannel"].commands["retry-count"],
            ["get", "PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.strip() == "3"

    @patch("subprocess.Popen", new_callable=SubprocessMock)
    def test_portchannel_retry_count_group_multi_asic(self, subprocessMock):
        """Test that portchannel_retry_count group sets up teamdctl_command for non-default namespace (multi-asic)"""
        runner = CliRunner()
        db = Db()
        # Don't pass teamdctl_command - let the group function set it up
        # Use a non-default namespace to cover the multi-asic code path
        obj = {'db': db.cfgdb, 'namespace': 'asic0'}

        subprocessMock.retryCountEnabled = True

        # Invoke through retry-count group command to trigger the group callback
        result = runner.invoke(
            config.config.commands["portchannel"].commands["retry-count"],
            ["get", "PortChannel1001"], obj=obj)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert result.output.strip() == "3"

    def test_show_interfaces_portchannel_info_portchannel_with_no_members(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel0004"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (re.sub(r'\s+', ' ', result.output.strip())) == (re.sub(
                r'\s+', ' ', EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_NO_MEMBERS_OUTPUT.strip()))

    def test_show_interfaces_portchannel_info_portchannel_with_deselected_member(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel0001"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (re.sub(r'\s+', ' ', result.output.strip())) == (re.sub(
                r'\s+', ' ', EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_DESELECTED_MEMBER_OUTPUT.strip()))

    def test_show_interfaces_portchannel_info_portchannel_with_selected_member(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel0002"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert (re.sub(r'\s+', ' ', result.output.strip())) == (re.sub(
                r'\s+', ' ', EXPECTED_SHOW_LACP_INFO_PORTCHANNEL_WITH_SELECTED_MEMBER_OUTPUT.strip()))

    def test_show_interfaces_portchannel_info_portchannel_non_exists(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               ["PortChannel107"], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        assert "No such PortChannel interface" in result.output

    def test_show_interfaces_portchannel_info(self):
        runner = CliRunner()
        db = Db()
        result = runner.invoke(show.cli.commands["interfaces"].commands["portchannel"].commands["info"],
                               [], obj=db, catch_exceptions=False)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

    @patch('clear.portchannel.clicommon.run_command')
    def test_clear_portchannel_statistics(self, run_command):
        runner = CliRunner()
        db = Db()
        # Clearing stats for all LAGs
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'], obj=db, catch_exceptions=False)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        # Clearing stats for specific PortChannel - Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'], ['PortChannel0001'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        run_command.assert_called_with('sudo teamdctl PortChannel0001 clear statistics', shell=True)
        run_command.reset_mock()

        # Clearing stats for specific PortChannel member - Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'],
                               ['PortChannel0001', 'Ethernet112'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        run_command.assert_called_with('sudo teamdctl PortChannel0001 clear statistics port Ethernet112', shell=True)
        run_command.reset_mock()

        # Clearing stats for specific PortChannel - Not Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'], ['PortChannel107'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        if "No such portchannel interface" in result.output:
            assert not run_command.called, "run_command should not be called when PortChannel is missing"

        # Clearing stats for specific PortChannel member - Not Exists
        result = runner.invoke(clear.cli.commands['portchannel'].commands['statistics'],
                               ['PortChannel0001', 'Ethernet4'], obj=db)
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0
        if "No such portchannel or portchannel member interface" in result.output:
            assert not run_command.called, "run_command should not be called when PortChannel is missing"

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
