#!/usr/bin/env python3
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest

from tests.testlib import on_time

from cmk.base.plugins.agent_based import veeam_cdp_jobs
from cmk.base.plugins.agent_based.agent_based_api.v1 import Result, Service, State, type_defs
from cmk.base.plugins.agent_based.agent_based_api.v1.type_defs import CheckResult, DiscoveryResult

DATA = [
    ["Test 1", "1632216559.73749", "Running"],
    ["Test 2", "1632216559.87806", "Failed"],
    ["Test 3", "1632216559.87806", "Stopped"],
    ["Test 4", "null", "Disabled"],
    ["Test 5", "1632216559,73749", "Running"],
]


@pytest.mark.parametrize(
    "data, result",
    [
        (
            DATA,
            [
                Service(item="Test 1"),
                Service(item="Test 2"),
                Service(item="Test 3"),
                Service(item="Test 4"),
                Service(item="Test 5"),
            ],
        ),
    ],
)
def test_veeam_cdp_jobs_discovery(
    data: type_defs.StringTable,
    result: DiscoveryResult,
) -> None:
    section = veeam_cdp_jobs.parse_veeam_cdp_jobs(data)
    assert list(veeam_cdp_jobs.discovery_veeam_cdp_jobs(section)) == result


@pytest.mark.parametrize(
    "item, params, data, result",
    [
        (
            "Test 1",
            veeam_cdp_jobs.CheckParams(age=(108000, 172800)),
            DATA,
            [
                Result(state=State.OK, summary="State: Running"),
                Result(state=State.OK, summary="Time since last CDP Run: 1 minute 40 seconds"),
            ],
        ),
        (
            "Test 2",
            veeam_cdp_jobs.CheckParams(age=(100, 300)),
            DATA,
            [
                Result(state=State.CRIT, summary="State: Failed"),
                Result(
                    state=State.WARN,
                    summary="Time since last CDP Run: 1 minute 40 seconds (warn/crit at 1 minute 40 seconds/5 minutes 0 seconds)",
                ),
            ],
        ),
        (
            "Test 3",
            veeam_cdp_jobs.CheckParams(age=(60, 80)),
            DATA,
            [
                Result(state=State.CRIT, summary="State: Stopped"),
                Result(
                    state=State.CRIT,
                    summary="Time since last CDP Run: 1 minute 40 seconds (warn/crit at 1 minute 0 seconds/1 minute 20 seconds)",
                ),
            ],
        ),
        (
            "Test 4",
            veeam_cdp_jobs.CheckParams(age=(60, 80)),
            DATA,
            [
                Result(state=State.OK, summary="State: Disabled"),
            ],
        ),
        (
            "Test 5",
            veeam_cdp_jobs.CheckParams(age=(108000, 172800)),
            DATA,
            [
                Result(state=State.OK, summary="State: Running"),
                Result(state=State.OK, summary="Time since last CDP Run: 1 minute 40 seconds"),
            ],
        ),
    ],
)
def test_veeam_cdp_jobs_check(
    item: str,
    params: veeam_cdp_jobs.CheckParams,
    data: type_defs.StringTable,
    result: CheckResult,
) -> None:
    with on_time(1632216660, "UTC"):
        section = veeam_cdp_jobs.parse_veeam_cdp_jobs(data)
        assert list(veeam_cdp_jobs.check_veeam_cdp_jobs(item, params, section)) == result
