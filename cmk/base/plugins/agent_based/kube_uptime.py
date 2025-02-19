#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


import time
from json import loads

from cmk.plugins.lib.kube import StartTime
from cmk.plugins.lib.uptime import Section

from .agent_based_api.v1 import register
from .agent_based_api.v1.type_defs import StringTable


def _parse_kube_start_time(now: float, string_table: StringTable) -> Section | None:
    if not string_table:
        return None
    return Section(uptime_sec=now - StartTime(**loads(string_table[0][0])).start_time, message=None)


def parse_kube_start_time(string_table: StringTable) -> Section | None:
    return _parse_kube_start_time(time.time(), string_table)


register.agent_section(
    name="kube_start_time_v1",
    parsed_section_name="uptime",
    parse_function=parse_kube_start_time,
)
