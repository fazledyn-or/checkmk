#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.base.check_api import LegacyCheckDefinition
from cmk.base.config import check_info
from cmk.base.plugins.agent_based.agent_based_api.v1 import SNMPTree

from cmk.plugins.lib.fortinet import DETECT_FORTIGATE


def inventory_fortigate_ipsecvpn(info):
    if len(info) > 0:
        return [(None, {})]
    return []


def check_fortigate_ipsecvpn(item, params, info):
    if isinstance(params, tuple):
        params = {"levels": params}

    tunnels_ignore_levels = params.get("tunnels_ignore_levels", [])

    tunnels_down = set()
    tunnels_ignored = set()
    for p2name, ent_status in info:
        if ent_status == "1":  # down(1), up(2)
            tunnels_down.add(p2name)
            if p2name in tunnels_ignore_levels:
                tunnels_ignored.add(p2name)

    num_total = len(info)
    num_down = len(tunnels_down)
    num_up = num_total - num_down

    num_ignored = len(tunnels_ignored)
    num_down_and_not_ignored = num_down - num_ignored

    infotext = "Total: %d, Up: %d, Down: %d, Ignored: %s" % (
        num_total,
        num_up,
        num_down,
        num_ignored,
    )

    warn, crit = params.get("levels", (None, None))
    status = 0
    if crit is not None and num_down_and_not_ignored >= crit:
        status = 2
    elif warn is not None and num_down_and_not_ignored >= warn:
        status = 1
    if status:
        infotext += f" (warn/crit at {warn}/{crit})"

    yield status, infotext, [("active_vpn_tunnels", num_up, "", "", 0, num_total)]

    long_output = []
    for title, tunnels in [
        ("Down and not ignored", set(tunnels_down) - set(tunnels_ignored)),
        ("Down", tunnels_down),
        ("Ignored", tunnels_ignored),
    ]:
        if tunnels:
            long_output.append("%s:" % title)
            long_output.append(", ".join(tunnels))
    if long_output:
        yield 0, "\n%s" % "\n".join(long_output)


check_info["fortigate_ipsecvpn"] = LegacyCheckDefinition(
    detect=DETECT_FORTIGATE,
    fetch=SNMPTree(
        base=".1.3.6.1.4.1.12356.101.12.2.2.1",
        oids=["3", "20"],
    ),
    service_name="VPN IPSec Tunnels",
    discovery_function=inventory_fortigate_ipsecvpn,
    check_function=check_fortigate_ipsecvpn,
    check_ruleset_name="ipsecvpn",
    check_default_parameters={
        "levels": (1, 2),
    },
)
