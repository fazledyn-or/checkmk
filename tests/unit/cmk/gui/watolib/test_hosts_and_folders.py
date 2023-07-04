#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import datetime
import os
import pprint
import shutil
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import freezegun
import pytest
from pytest import MonkeyPatch

from tests.testlib import on_time

from cmk.utils.exceptions import MKGeneralException
from cmk.utils.hostaddress import HostName
from cmk.utils.redis import disable_redis
from cmk.utils.store.host_storage import ContactgroupName
from cmk.utils.user import UserId

import cmk.gui.watolib.hosts_and_folders as hosts_and_folders
from cmk.gui import userdb
from cmk.gui.config import active_config
from cmk.gui.ctx_stack import g
from cmk.gui.exceptions import MKUserError
from cmk.gui.logged_in import user as logged_in_user
from cmk.gui.watolib.bakery import has_agent_bakery
from cmk.gui.watolib.hosts_and_folders import Folder, folder_tree
from cmk.gui.watolib.search import MatchItem


@pytest.fixture(autouse=True)
def test_env(with_admin_login: UserId, load_config: None) -> Iterator[None]:
    # Ensure we have clean folder/host caches
    tree = folder_tree()
    tree.invalidate_caches()

    yield

    # Cleanup WATO folders created by the test
    shutil.rmtree(tree.root_folder().filesystem_path(), ignore_errors=True)
    os.makedirs(tree.root_folder().filesystem_path())


@pytest.fixture(autouse=True)
def fake_start_bake_agents(monkeypatch: MonkeyPatch) -> None:
    if not has_agent_bakery():
        return

    import cmk.gui.cee.plugins.wato.agent_bakery.misc as agent_bakery  # pylint: disable=no-name-in-module

    def _fake_start_bake_agents(host_names, signing_credentials):
        pass

    monkeypatch.setattr(agent_bakery, "start_bake_agents", _fake_start_bake_agents)


@pytest.mark.parametrize(
    "attributes,expected_tags",
    [
        (
            {
                "tag_snmp": "no-snmp",
                "tag_agent": "no-agent",
                "site": "ding",
            },
            {
                "address_family": "ip-v4-only",
                "agent": "no-agent",
                "ip-v4": "ip-v4",
                "piggyback": "auto-piggyback",
                "ping": "ping",
                "site": "ding",
                "snmp_ds": "no-snmp",
            },
        ),
        (
            {
                "tag_snmp": "no-snmp",
                "tag_agent": "no-agent",
                "tag_address_family": "no-ip",
            },
            {
                "address_family": "no-ip",
                "agent": "no-agent",
                "piggyback": "auto-piggyback",
                "site": "NO_SITE",
                "snmp_ds": "no-snmp",
            },
        ),
        (
            {
                "site": False,
            },
            {
                "address_family": "ip-v4-only",
                "agent": "cmk-agent",
                "checkmk-agent": "checkmk-agent",
                "ip-v4": "ip-v4",
                "piggyback": "auto-piggyback",
                "site": "",
                "snmp_ds": "no-snmp",
                "tcp": "tcp",
            },
        ),
    ],
)
def test_host_tags(attributes: dict, expected_tags: dict[str, str]) -> None:
    folder = folder_tree().root_folder()
    host = hosts_and_folders.Host(folder, HostName("test-host"), attributes, cluster_nodes=None)

    assert host.tag_groups() == expected_tags


@pytest.mark.parametrize(
    "attributes,result",
    [
        (
            {
                "tag_snmp_ds": "no-snmp",
                "tag_agent": "no-agent",
            },
            True,
        ),
        (
            {
                "tag_snmp_ds": "no-snmp",
                "tag_agent": "cmk-agent",
            },
            False,
        ),
        (
            {
                "tag_snmp_ds": "no-snmp",
                "tag_agent": "no-agent",
                "tag_address_family": "no-ip",
            },
            False,
        ),
    ],
)
def test_host_is_ping_host(attributes: dict[str, object], result: bool) -> None:
    folder = folder_tree().root_folder()
    host = hosts_and_folders.Host(folder, HostName("test-host"), attributes, cluster_nodes=None)

    assert host.is_ping_host() == result


@pytest.mark.parametrize(
    "attributes",
    [
        {
            "tag_snmp_ds": "no-snmp",
            "tag_agent": "no-agent",
            "alias": "testalias",
            "parents": ["ding", "dong"],
        }
    ],
)
def test_write_and_read_host_attributes(attributes: dict[str, str | list[str]]) -> None:
    tree = folder_tree()
    # Used to write the data
    write_data_folder = hosts_and_folders.Folder.load(
        tree=tree, name="testfolder", parent_folder=tree.root_folder()
    )

    # Used to read the previously written data
    read_data_folder = hosts_and_folders.Folder.load(
        tree=tree, name="testfolder", parent_folder=tree.root_folder()
    )

    # Write data
    write_data_folder.create_hosts([(HostName("testhost"), attributes, [])])
    write_folder_hosts = write_data_folder.hosts()
    assert len(write_folder_hosts) == 1

    # Read data back
    read_folder_hosts = read_data_folder.hosts()
    assert len(read_folder_hosts) == 1
    for _, host in read_folder_hosts.items():
        assert host.attributes() == {
            "meta_data": host.attributes()["meta_data"],
            **attributes,
        }


@contextmanager
def in_chdir(directory: str) -> Iterator[None]:
    cur = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(cur)


def test_create_nested_folders(request_context: None) -> None:
    with in_chdir("/"):
        tree = folder_tree()
        root = tree.root_folder()

        folder1 = hosts_and_folders.Folder.new(tree=tree, name="folder1", parent_folder=root)
        folder1.persist_instance()

        folder2 = hosts_and_folders.Folder.new(tree=tree, name="folder2", parent_folder=folder1)
        folder2.persist_instance()

        shutil.rmtree(os.path.dirname(folder1.wato_info_path()))


def test_eq_operation(request_context: None) -> None:
    with in_chdir("/"):
        tree = folder_tree()
        root = tree.root_folder()
        folder1 = hosts_and_folders.Folder.new(tree=tree, name="folder1", parent_folder=root)
        folder1.persist_instance()

        folder1_new = hosts_and_folders.Folder.load(tree=tree, name="folder1", parent_folder=root)

        assert folder1 == folder1_new
        assert id(folder1) != id(folder1_new)
        assert folder1 in [folder1_new]

        folder2 = hosts_and_folders.Folder.new(tree=tree, name="folder2", parent_folder=folder1)
        folder2.persist_instance()

        assert folder1 not in [folder2]


@pytest.mark.parametrize(
    "protocol,host_attribute,base_variable,credentials,folder_credentials",
    [
        ("snmp", "management_snmp_community", "management_snmp_credentials", "HOST", "FOLDER"),
        (
            "ipmi",
            "management_ipmi_credentials",
            "management_ipmi_credentials",
            {
                "username": "USER",
                "password": "PASS",
            },
            {
                "username": "FOLDERUSER",
                "password": "FOLDERPASS",
            },
        ),
    ],
)
def test_mgmt_inherit_credentials_explicit_host(
    protocol: str,
    host_attribute: str,
    base_variable: str,
    credentials: str | dict[str, str],
    folder_credentials: str | dict[str, str],
) -> None:
    folder = folder_tree().root_folder()
    folder.set_attribute(host_attribute, folder_credentials)

    folder.create_hosts(
        [
            (
                HostName("test-host"),
                {
                    "ipaddress": "127.0.0.1",
                    "management_protocol": protocol,
                    host_attribute: credentials,
                },
                [],
            )
        ],
    )

    data = folder._load_hosts_file()
    assert data is not None
    assert data["management_protocol"]["test-host"] == protocol
    assert data[base_variable]["test-host"] == credentials


@pytest.mark.parametrize(
    "protocol,host_attribute,base_variable,folder_credentials",
    [
        ("snmp", "management_snmp_community", "management_snmp_credentials", "FOLDER"),
        (
            "ipmi",
            "management_ipmi_credentials",
            "management_ipmi_credentials",
            {
                "username": "FOLDERUSER",
                "password": "FOLDERPASS",
            },
        ),
    ],
)
def test_mgmt_inherit_credentials(
    protocol: str,
    host_attribute: str,
    base_variable: str,
    folder_credentials: str | dict[str, str],
) -> None:
    folder = folder_tree().root_folder()
    folder.set_attribute(host_attribute, folder_credentials)

    folder.create_hosts(
        [
            (
                HostName("mgmt-host"),
                {
                    "ipaddress": "127.0.0.1",
                    "management_protocol": protocol,
                },
                [],
            )
        ],
    )

    data = folder._load_hosts_file()
    assert data is not None
    assert data["management_protocol"]["mgmt-host"] == protocol
    assert data[base_variable]["mgmt-host"] == folder_credentials


@pytest.mark.parametrize(
    "protocol,host_attribute,base_variable,credentials,folder_credentials",
    [
        ("snmp", "management_snmp_community", "management_snmp_credentials", "HOST", "FOLDER"),
        (
            "ipmi",
            "management_ipmi_credentials",
            "management_ipmi_credentials",
            {
                "username": "USER",
                "password": "PASS",
            },
            {
                "username": "FOLDERUSER",
                "password": "FOLDERPASS",
            },
        ),
    ],
)
def test_mgmt_inherit_protocol_explicit_host(
    protocol: str,
    host_attribute: str,
    base_variable: str,
    credentials: str | dict[str, str],
    folder_credentials: str | dict[str, str],
) -> None:
    folder = folder_tree().root_folder()
    folder.set_attribute("management_protocol", None)
    folder.set_attribute(host_attribute, folder_credentials)

    folder.create_hosts(
        [
            (
                HostName("mgmt-host"),
                {
                    "ipaddress": "127.0.0.1",
                    "management_protocol": protocol,
                    host_attribute: credentials,
                },
                [],
            )
        ],
    )

    data = folder._load_hosts_file()
    assert data is not None
    assert data["management_protocol"]["mgmt-host"] == protocol
    assert data[base_variable]["mgmt-host"] == credentials


@pytest.mark.parametrize(
    "protocol,host_attribute,base_variable,folder_credentials",
    [
        ("snmp", "management_snmp_community", "management_snmp_credentials", "FOLDER"),
        (
            "ipmi",
            "management_ipmi_credentials",
            "management_ipmi_credentials",
            {
                "username": "FOLDERUSER",
                "password": "FOLDERPASS",
            },
        ),
    ],
)
def test_mgmt_inherit_protocol(
    protocol: str,
    host_attribute: str,
    base_variable: str,
    folder_credentials: str | dict[str, str],
) -> None:
    folder = folder_tree().root_folder()
    folder.set_attribute("management_protocol", protocol)
    folder.set_attribute(host_attribute, folder_credentials)

    folder.create_hosts(
        [
            (
                HostName("mgmt-host"),
                {
                    "ipaddress": "127.0.0.1",
                },
                [],
            )
        ],
    )

    data = folder._load_hosts_file()
    assert data is not None
    assert data["management_protocol"]["mgmt-host"] == protocol
    assert data[base_variable]["mgmt-host"] == folder_credentials


@pytest.fixture(name="patch_may")
def fixture_patch_may(mocker: MagicMock) -> None:
    def prefixed_title(self_: hosts_and_folders.CREFolder, current_depth: int, pretty: bool) -> str:
        return "_" * current_depth + self_.title()

    mocker.patch.object(hosts_and_folders.Folder, "_prefixed_title", prefixed_title)

    def may(self_, _permission):
        return getattr(self_, "_may_see", True)

    mocker.patch.object(hosts_and_folders.PermissionChecker, "may", may)


def only_root() -> hosts_and_folders.CREFolder:
    root_folder = folder_tree().root_folder()
    root_folder._loaded_subfolders = {}
    return root_folder


def three_levels() -> hosts_and_folders.CREFolder:
    main = folder_tree().root_folder()

    a = main.create_subfolder("a", title="A", attributes={})
    a.create_subfolder("c", title="C", attributes={})
    a.create_subfolder("d", title="D", attributes={})

    b = main.create_subfolder("b", title="B", attributes={})
    e = b.create_subfolder("e", title="E", attributes={})
    e.create_subfolder("f", title="F", attributes={})

    return main


def three_levels_leaf_permissions() -> hosts_and_folders.CREFolder:
    main = folder_tree().root_folder()

    # Attribute only used for testing
    main.permissions._may_see = False  # type: ignore[attr-defined]

    a = main.create_subfolder("a", title="A", attributes={})
    a.permissions._may_see = False  # type: ignore[attr-defined]
    c = a.create_subfolder("c", title="C", attributes={})
    c.permissions._may_see = False  # type: ignore[attr-defined]
    a.create_subfolder("d", title="D", attributes={})

    b = main.create_subfolder("b", title="B", attributes={})
    b.permissions._may_see = False  # type: ignore[attr-defined]
    e = b.create_subfolder("e", title="E", attributes={})
    e.permissions._may_see = False  # type: ignore[attr-defined]
    e.create_subfolder("f", title="F", attributes={})

    return main


@pytest.mark.parametrize(
    "actual_builder,expected",
    [
        (only_root, [("", "Main")]),
        (
            three_levels,
            [
                ("", "Main"),
                ("a", "_A"),
                ("a/c", "__C"),
                ("a/d", "__D"),
                ("b", "_B"),
                ("b/e", "__E"),
                ("b/e/f", "___F"),
            ],
        ),
        (
            three_levels_leaf_permissions,
            [
                ("", "Main"),
                ("a", "_A"),
                ("a/d", "__D"),
                ("b", "_B"),
                ("b/e", "__E"),
                ("b/e/f", "___F"),
            ],
        ),
    ],
)
@pytest.mark.usefixtures("patch_may")
def test_recursive_subfolder_choices(
    monkeypatch: MonkeyPatch,
    actual_builder: Callable[[], hosts_and_folders.CREFolder],
    expected: list[tuple[str, str]],
) -> None:
    with monkeypatch.context() as m:
        m.setattr(active_config, "wato_hide_folders_without_read_permissions", True)
        assert actual_builder().recursive_subfolder_choices() == expected


@pytest.mark.usefixtures("patch_may")
def test_recursive_subfolder_choices_function_calls(
    monkeypatch: MonkeyPatch, mocker: MagicMock
) -> None:
    """Every folder should only be visited once"""
    with monkeypatch.context() as m:
        m.setattr(active_config, "wato_hide_folders_without_read_permissions", True)
        spy = mocker.spy(hosts_and_folders.Folder, "_walk_tree")
        tree = three_levels_leaf_permissions()
        tree.recursive_subfolder_choices()
        assert spy.call_count == 7


def test_subfolder_creation() -> None:
    folder = folder_tree().root_folder()
    folder.create_subfolder("foo", "Foo Folder", {})

    # Upon instantiation, all the subfolders should be already known.
    folder = folder_tree().root_folder()
    assert len(folder._subfolders) == 1


def test_match_item_generator_hosts() -> None:
    assert list(
        hosts_and_folders.MatchItemGeneratorHosts(
            HostName("hosts"),
            lambda: {
                HostName("host"): {
                    "edit_url": "some_url",
                    "alias": "alias",
                    "ipaddress": "1.2.3.4",
                    "ipv6address": "",
                    "additional_ipv4addresses": ["5.6.7.8"],
                    "additional_ipv6addresses": [],
                },
            },
        ).generate_match_items()
    ) == [
        MatchItem(
            title="host",
            topic="Hosts",
            url="some_url",
            match_texts=["host", "alias", "1.2.3.4", "5.6.7.8"],
        )
    ]


@dataclass
class _TreeStructure:
    path: str
    attributes: dict[str, Any]
    subfolders: list["_TreeStructure"]
    num_hosts: int = 0


def make_monkeyfree_folder(
    tree_structure: _TreeStructure, parent: hosts_and_folders.CREFolder | None = None
) -> hosts_and_folders.CREFolder:
    tree = hosts_and_folders.folder_tree()
    if parent is None:
        new_folder = tree.root_folder()
        new_folder._attributes = tree_structure.attributes
    else:
        new_folder = hosts_and_folders.CREFolder.new(
            tree=tree,
            name=tree_structure.path,
            parent_folder=parent,
            title=f"Title of {tree_structure.path}",
            attributes=tree_structure.attributes,
        )

    # Small monkeys :(
    new_folder._num_hosts = tree_structure.num_hosts
    new_folder._path = tree_structure.path

    for subtree_structure in tree_structure.subfolders:
        new_folder._subfolders[subtree_structure.path] = make_monkeyfree_folder(
            subtree_structure, new_folder
        )
        new_folder._path = tree_structure.path

    return new_folder


def dump_wato_folder_structure(wato_folder: hosts_and_folders.CREFolder) -> None:
    # Debug function to have a look at the internal folder tree structure
    sys.stdout.write("\n")

    def dump_structure(wato_folder: hosts_and_folders.CREFolder, indent: int = 0) -> None:
        indent_space = " " * indent * 6
        sys.stdout.write(f"{indent_space + '->' + str(wato_folder):80} {wato_folder.path()}\n")
        sys.stdout.write(
            "\n".join(
                f"{indent_space}  {x}" for x in pprint.pformat(wato_folder.attributes()).split("\n")
            )
            + "\n"
        )
        for subfolder in wato_folder.subfolders():
            dump_structure(subfolder, indent + 1)

    dump_structure(wato_folder)


@pytest.mark.parametrize(
    "structure,testfolder_expected_groups",
    [
        # Basic inheritance
        (
            _TreeStructure(
                "",
                {
                    "contactgroups": {
                        "groups": ["group1"],
                        "recurse_perms": False,
                        "use": False,
                        "use_for_services": False,
                        "recurse_use": False,
                    }
                },
                [
                    _TreeStructure("sub1", {}, [_TreeStructure("testfolder", {}, [])]),
                ],
            ),
            {"group1"},
        ),
        # Blocked inheritance by sub1
        (
            _TreeStructure(
                "",
                {
                    "contactgroups": {
                        "groups": ["group1"],
                        "recurse_perms": False,
                        "use": False,
                        "use_for_services": False,
                        "recurse_use": False,
                    }
                },
                [
                    _TreeStructure(
                        "sub1",
                        {
                            "contactgroups": {
                                "groups": [],
                                "recurse_perms": False,
                                "use": False,
                                "use_for_services": False,
                                "recurse_use": False,
                            }
                        },
                        [_TreeStructure("testfolder", {}, [])],
                    ),
                ],
            ),
            set(),
        ),
        # Used recurs_perms(bypasses inheritance)
        (
            _TreeStructure(
                "",
                {
                    "contactgroups": {
                        "groups": ["group1"],
                        "recurse_perms": True,
                        "use": False,
                        "use_for_services": False,
                        "recurse_use": False,
                    }
                },
                [
                    _TreeStructure(
                        "sub1",
                        {
                            "contactgroups": {
                                "groups": [],
                                "recurse_perms": False,
                                "use": False,
                                "use_for_services": False,
                                "recurse_use": False,
                            }
                        },
                        [_TreeStructure("testfolder", {}, [])],
                    ),
                ],
            ),
            {"group1"},
        ),
        # Used recurs_perms (bypasses inheritance), test multiple groups
        (
            _TreeStructure(
                "",
                {
                    "contactgroups": {
                        "groups": ["group1"],
                        "recurse_perms": True,
                        "use": False,
                        "use_for_services": False,
                        "recurse_use": False,
                    }
                },
                [
                    _TreeStructure(
                        "sub1",
                        {
                            "contactgroups": {
                                "groups": ["group2"],
                                "recurse_perms": False,
                                "use": False,
                                "use_for_services": False,
                                "recurse_use": False,
                            }
                        },
                        [_TreeStructure("testfolder", {}, [])],
                    ),
                ],
            ),
            {"group1", "group2"},
        ),
    ],
)
def test_folder_permissions(
    structure: _TreeStructure, testfolder_expected_groups: set[str]
) -> None:
    with disable_redis():
        wato_folder = make_monkeyfree_folder(structure)
        # dump_wato_folder_structure(wato_folder)
        testfolder = wato_folder._subfolders["sub1"]._subfolders["testfolder"]
        permitted_groups_cre_folder, _host_contact_groups, _use_for_service = testfolder.groups()
        assert permitted_groups_cre_folder == testfolder_expected_groups

        all_folders = _convert_folder_tree_to_all_folders(wato_folder)
        permitted_groups_bulk = hosts_and_folders._get_permitted_groups_of_all_folders(all_folders)
        assert permitted_groups_bulk["sub1/testfolder"].actual_groups == testfolder_expected_groups


def _convert_folder_tree_to_all_folders(
    root_folder: hosts_and_folders.CREFolder,
) -> dict[hosts_and_folders.PathWithoutSlash, hosts_and_folders.CREFolder]:
    all_folders = {}

    def parse_folder(folder):
        all_folders[folder.path()] = folder
        for subfolder in folder.subfolders():
            parse_folder(subfolder)

    parse_folder(root_folder)
    return all_folders


@dataclass
class _UserTest:
    contactgroups: list[ContactgroupName]
    hide_folders_without_permission: bool
    expected_num_hosts: int
    fix_legacy_visibility: bool = False


@contextmanager
def hide_folders_without_permission(do_hide: bool) -> Iterator[None]:
    old_value = active_config.wato_hide_folders_without_read_permissions
    try:
        active_config.wato_hide_folders_without_read_permissions = do_hide
        yield
    finally:
        active_config.wato_hide_folders_without_read_permissions = old_value


def _default_groups(configured_groups: list[ContactgroupName]) -> dict[str, Any]:
    return {
        "contactgroups": {
            "groups": configured_groups,
            "recurse_perms": False,
            "use": False,
            "use_for_services": False,
            "recurse_use": False,
        }
    }


group_tree_structure = _TreeStructure(
    "",
    _default_groups(["group1"]),
    [
        _TreeStructure(
            "sub1.1",
            {},
            [
                _TreeStructure(
                    "sub2.1",
                    _default_groups(["supersecret_group"]),
                    [],
                    100,
                ),
            ],
            8,
        ),
        _TreeStructure(
            "sub1.2",
            _default_groups(["group2"]),
            [],
            3,
        ),
        _TreeStructure(
            "sub1.3",
            _default_groups(["group1", "group3"]),
            [],
            1,
        ),
    ],
    5,
)

group_tree_test = (
    group_tree_structure,
    [
        _UserTest([], True, 0, True),
        _UserTest(["nomatch"], True, 0, True),
        _UserTest(["group2"], True, 3, True),
        _UserTest(["group1", "group2"], True, 17, False),
        _UserTest(["group1", "group2"], False, 117, False),
    ],
)


@pytest.mark.usefixtures("with_user_login")
@pytest.mark.parametrize(
    "structure, user_tests",
    [group_tree_test],
)
def test_num_hosts_normal_user(
    structure: _TreeStructure, user_tests: list[_UserTest], monkeypatch: MonkeyPatch
) -> None:
    with disable_redis():
        for user_test in user_tests:
            _run_num_host_test(
                structure,
                user_test,
                user_test.expected_num_hosts,
                False,
                monkeypatch,
            )


@pytest.mark.usefixtures("with_admin_login")
@pytest.mark.parametrize(
    "structure, user_tests",
    [group_tree_test],
)
def test_num_hosts_admin_user(
    structure: _TreeStructure, user_tests: list[_UserTest], monkeypatch: MonkeyPatch
) -> None:
    with disable_redis():
        for user_test in user_tests:
            _run_num_host_test(structure, user_test, 117, True, monkeypatch)


def _run_num_host_test(
    structure: _TreeStructure,
    user_test: _UserTest,
    expected_host_count: int,
    is_admin: bool,
    monkeypatch: MonkeyPatch,
) -> None:
    wato_folder = make_monkeyfree_folder(structure)
    with hide_folders_without_permission(user_test.hide_folders_without_permission):
        # The algorithm implemented in CREFolder actually computes the num_hosts_recursively wrong.
        # It does not exclude hosts in the questioned base folder, even when it should adhere
        # the visibility permissions. This error is not visible in the GUI since another(..)
        # function filters those folders in advance
        legacy_base_folder_host_offset = (
            0
            if (not user_test.fix_legacy_visibility or is_admin)
            else (structure.num_hosts if user_test.hide_folders_without_permission else 0)
        )

        # Old mechanism
        with patch.dict(logged_in_user._attributes, {"contactgroups": user_test.contactgroups}):
            assert (
                wato_folder.num_hosts_recursively()
                == expected_host_count + legacy_base_folder_host_offset
            )

        # New mechanism
        monkeypatch.setattr(userdb, "contactgroups_of_user", lambda u: user_test.contactgroups)
        with get_fake_setup_redis_client(
            monkeypatch,
            _convert_folder_tree_to_all_folders(wato_folder),
            [_fake_redis_num_hosts_answer(wato_folder)],
        ):
            assert wato_folder.num_hosts_recursively() == expected_host_count


def _fake_redis_num_hosts_answer(wato_folder: hosts_and_folders.CREFolder) -> list[list[str]]:
    redis_answer = []
    for folder in _convert_folder_tree_to_all_folders(wato_folder).values():
        redis_answer.extend([",".join(folder.groups()[0]), str(folder._num_hosts)])
    return [redis_answer]


class MockRedisClient:
    def __init__(self, answers: list[list[list[str]]]) -> None:
        class FakePipeline:
            def __init__(self, answers: list[list[list[str]]]) -> None:
                self._answers = answers

            def execute(self):
                return self._answers.pop(0)

            def __getattr__(self, name):
                return lambda *args, **kwargs: None

        self._fake_pipeline = FakePipeline(answers)
        self._answers = answers

    def __getattr__(self, name):
        if name == "pipeline":
            return lambda: self._fake_pipeline

        return lambda *args, **kwargs: lambda *args, **kwargs: None


@contextmanager
def get_fake_setup_redis_client(
    monkeypatch: MonkeyPatch,
    all_folders: dict[hosts_and_folders.PathWithoutSlash, hosts_and_folders.CREFolder],
    redis_answers: list[list[list[str]]],
) -> Iterator[MockRedisClient]:
    monkeypatch.setattr(hosts_and_folders, "may_use_redis", lambda: True)
    mock_redis_client = MockRedisClient(redis_answers)
    monkeypatch.setattr(hosts_and_folders._RedisHelper, "_cache_integrity_ok", lambda x: True)
    tree = folder_tree()
    redis_helper = hosts_and_folders.get_wato_redis_client(tree)
    monkeypatch.setattr(redis_helper, "_client", mock_redis_client)
    monkeypatch.setattr(redis_helper, "_folder_paths", [f"{x}/" for x in all_folders.keys()])
    monkeypatch.setattr(
        redis_helper,
        "_folder_metadata",
        {
            f"{x}/": hosts_and_folders.FolderMetaData(tree, f"{x}/", "nix", "nix", [])
            for x in all_folders.keys()
        },
    )
    try:
        yield mock_redis_client
    finally:
        monkeypatch.setattr(hosts_and_folders, "may_use_redis", lambda: False)
        # I have no idea if this is actually working..
        monkeypatch.undo()


@pytest.mark.usefixtures("with_admin_login")
def test_load_redis_folders_on_demand(monkeypatch: MonkeyPatch) -> None:
    wato_folder = make_monkeyfree_folder(group_tree_structure)
    folder_tree().invalidate_caches()
    with get_fake_setup_redis_client(
        monkeypatch, _convert_folder_tree_to_all_folders(wato_folder), []
    ):
        folder_tree().all_folders()
        # Check if wato_folders class matches
        assert isinstance(g.wato_folders, hosts_and_folders.WATOFoldersOnDemand)
        # Check if item is None
        assert g.wato_folders._raw_dict["sub1.1"] is None
        # Check if item is generated on access
        assert isinstance(g.wato_folders["sub1.1"], hosts_and_folders.CREFolder)
        # Check if item is now set in dict
        assert isinstance(g.wato_folders._raw_dict["sub1.1"], hosts_and_folders.CREFolder)

        # Check if other folder is still None
        assert g.wato_folders._raw_dict["sub1.2"] is None
        # Check if parent(main) folder got instantiated as well
        assert isinstance(g.wato_folders._raw_dict[""], hosts_and_folders.CREFolder)


def test_folder_exists() -> None:
    tree = folder_tree()
    tree.root_folder().create_subfolder("foo", "foo", {}).create_subfolder("bar", "bar", {})
    assert tree.folder_exists("foo")
    assert tree.folder_exists("foo/bar")
    assert not tree.folder_exists("bar")
    assert not tree.folder_exists("foo/foobar")
    with pytest.raises(MKUserError):
        tree.folder_exists("../wato")


def test_folder_access() -> None:
    tree = folder_tree()
    tree.root_folder().create_subfolder("foo", "foo", {}).create_subfolder("bar", "bar", {})
    assert isinstance(tree.folder("foo/bar"), hosts_and_folders.CREFolder)
    assert isinstance(tree.folder(""), hosts_and_folders.CREFolder)
    with pytest.raises(MKGeneralException):
        tree.folder("unknown_folder")


def test_new_empty_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID("a8098c1a-f86e-11da-bd1a-00112444be1e"))
    tree = folder_tree()
    with on_time("2018-01-10 02:00:00", "CET"):
        folder = Folder.new(
            tree=tree,
            name="bla",
            title="Bla",
            attributes={},
            parent_folder=tree.root_folder(),
        )
    assert folder.name() == "bla"
    assert folder.id() == "a8098c1af86e11dabd1a00112444be1e"
    assert folder.title() == "Bla"
    assert folder.attributes() == {
        "meta_data": {
            "created_at": 1515549600.0,
            "created_by": None,
            "updated_at": 1515549600.0,
        }
    }


def test_new_loaded_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID("c6bda767ae5c47038f73d8906fb91bb4"))

    tree = folder_tree()
    with on_time("2018-01-10 02:00:00", "CET"):
        folder1 = Folder.new(tree=tree, name="folder1", parent_folder=tree.root_folder())
        folder1.persist_instance()
        tree.invalidate_caches()

    folder = Folder.load(tree=tree, name="folder1", parent_folder=tree.root_folder())
    assert folder.name() == "folder1"
    assert folder.id() == "c6bda767ae5c47038f73d8906fb91bb4"
    assert folder.title() == "folder1"
    assert folder.attributes() == {
        "meta_data": {
            "created_at": 1515549600.0,
            "created_by": None,
            "updated_at": 1515549600.0,
        }
    }


@pytest.mark.parametrize(
    "allowed,last_end,next_time",
    [
        (((0, 0), (24, 0)), None, 1515549600.0),
        (
            ((0, 0), (24, 0)),
            1515549600.0,
            1515549900.0,
        ),
        (((20, 0), (24, 0)), None, 1515610800.0),
        ([((0, 0), (2, 0)), ((20, 0), (22, 0))], None, 1515610800.0),
        ([((0, 0), (2, 0)), ((20, 0), (22, 0))], 1515621600.0, 1515625200.0),
    ],
)
def test_next_network_scan_at(
    allowed: object,
    last_end: float | None,
    next_time: float,
) -> None:
    tree = folder_tree()
    folder = Folder.new(
        tree=tree,
        parent_folder=tree.root_folder(),
        name="bla",
        title="Bla",
        attributes={
            "network_scan": {
                "exclude_ranges": [],
                "ip_ranges": [("ip_range", ("10.3.1.1", "10.3.1.100"))],
                "run_as": UserId("cmkadmin"),
                "scan_interval": 300,
                "set_ipaddress": True,
                "tag_criticality": "offline",
                "time_allowed": allowed,
            },
            "network_scan_result": {
                "end": last_end,
            },
        },
    )

    with on_time("2018-01-10 02:00:00", "CET"):
        assert folder.next_network_scan_at() == next_time


@pytest.mark.usefixtures("request_context")
def test_folder_times() -> None:
    tree = folder_tree()
    root = tree.root_folder()

    with freezegun.freeze_time(datetime.datetime(2020, 2, 2, 2, 2, 2)):
        current = time.time()
        Folder.new(tree=tree, name="test", parent_folder=root).save()
        folder = Folder.load(tree=tree, name="test", parent_folder=root)
        folder.save()

    meta_data = folder.attributes()["meta_data"]
    assert int(meta_data["created_at"]) == int(current)
    assert int(meta_data["updated_at"]) == int(current)

    folder.persist_instance()
    assert int(meta_data["updated_at"]) > int(current)
