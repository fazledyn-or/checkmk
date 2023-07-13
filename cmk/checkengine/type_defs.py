#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""Package containing the fetchers to the data sources."""

import enum
from collections.abc import Sequence
from typing import Final

from cmk.utils.sectionname import HostSection, SectionName

__all__ = ["NO_SELECTION", "SectionNameCollection"]


# Note that the inner Sequence[str] to AgentRawDataSectionElem
# is only **artificially** different from AgentRawData and
# obtained approximatively with `raw_data.decode("utf-8").split()`!
AgentRawDataSectionElem = Sequence[str]
AgentRawDataSection = HostSection[Sequence[AgentRawDataSectionElem]]


class SelectionType(enum.Enum):
    NONE = enum.auto()


SectionNameCollection = SelectionType | frozenset[SectionName]
# If preselected sections are given, we assume that we are interested in these
# and only these sections, so we may omit others and in the SNMP case
# must try to fetch them (regardles of detection).

NO_SELECTION: Final = SelectionType.NONE
