#!/usr/bin/env python3
# Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""
The "render" namespace adds functions to render values in a human readable way.

All of the render functions take a single numerical value as an argument, and return
a string.
"""

# pylint: disable=duplicate-code

from ..v1.render import (  # pylint: disable=redefined-builtin
    bytes,
    date,
    datetime,
    disksize,
    filesize,
    frequency,
    iobandwidth,
    networkbandwidth,
    nicspeed,
    percent,
    timespan,
)

__all__ = [
    "bytes",
    "date",
    "datetime",
    "disksize",
    "filesize",
    "frequency",
    "iobandwidth",
    "networkbandwidth",
    "nicspeed",
    "percent",
    "timespan",
]
