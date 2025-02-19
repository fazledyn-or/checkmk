#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# Agent output and things to know:

# hd5                 boot       1       2       2    closed/syncd  N/A
# hd6                 paging     65      130     2    open/syncd    N/A
# hd8                 jfs2log    1       2       2    open/syncd    N/A
# hd4                 jfs2       1       2       2    open/syncd    /
# hd2                 jfs2       5       10      2    open/syncd    /usr
# hd9var              jfs2       3       6       2    open/syncd    /var
# hd3                 jfs2       2       4       2    open/syncd    /tmp
# hd1                 jfs2       1       2       2    open/syncd    /home
# hd10opt             jfs2       3       6       2    open/syncd    /opt
# hd11admin           jfs2       1       2       2    open/syncd    /admin
# lg_dumplv           sysdump    6       6       1    open/syncd    N/A
# livedump            jfs2       1       2       2    open/syncd    /var/adm/ras/livedump
# lvwork              jfs2       1       2       2    open/syncd    /work
# lvbackup            jfs2       200     200     1    open/syncd    /backup
# fwdump              jfs2       5       5       1    open/syncd    /var/adm/ras/platform
# lvoracle            jfs2       30      30      1    open/syncd    /oracle

# hd5 which contains the boot kernel is normally always closed (but it doesn't
# matter IF it's closed.

# row3: 1 means it alloceted one lvm logical extent (called partition on AIX), so
# it's likely 256MB in size.
# row4: 2 means it uses two physical extents. So if it uses two physical for
# one logical ... yeah, a mirror

# row5: 2 means that the volume uses two physical volumes to store those
# extents. So the mirror isn't on the same disk if it dies.

# row6: here open/syncd is OK for every active volume

# lvmconf = {
#    rootvg : {
#         hd5 : ("boot", 1, 2, 2, "closed/syncd", None)
#         hd4 : ("/",    1, 2, 2, "open/syncd",   "/")
#    }
# }


# mypy: disable-error-code="var-annotated"

from cmk.base.check_api import LegacyCheckDefinition
from cmk.base.config import check_info


def parse_aix_lvm(info):
    lvmconf = {}
    for line in info:
        if len(line) == 1:
            vgname = line[0][:-1]
            lvmconf.update({vgname: {}})
        # Some versions send a title line "LV NAME  ..."
        elif line[0] == "LV" and line[1] == "NAME":
            continue
        else:
            lv, lvtype, num_lp, num_pp, num_pv, act_state, mountpoint = line
            # split lv state into two relevant values
            activation, mirror = act_state.split("/")
            if mountpoint == "N/A":
                mountpoint = None
            lvmconf[vgname].update(
                {
                    lv: (
                        lvtype,
                        int(num_lp),
                        int(num_pp),
                        int(num_pv),
                        activation,
                        mirror,
                        mountpoint,
                    )
                }
            )
    return lvmconf


def inventory_aix_lvm(info):
    inventory = []
    for vg, volumes in parse_aix_lvm(info).items():
        for lv in volumes:
            # inventory.append(("%s/%s" % (vg, lv), ('%s' % volumes[lv][4],)))
            inventory.append((f"{vg}/{lv}", None))
    return inventory


def check_aix_lvm(item, _no_params, info):
    # Get ready to find our item and settings.
    # target_activation = params
    target_vg, target_lv = item.split("/")

    # Get structured LVM info
    lvmconf = parse_aix_lvm(info)

    if target_vg in lvmconf and target_lv in lvmconf[target_vg]:
        msgtxt = []
        state = 0

        lvtype, num_lp, num_pp, num_pv, activation, mirror, _mountpoint = lvmconf[target_vg][
            target_lv
        ]

        # Test if the volume is mirrored.
        # Yes? Test for an even distribution of PP's over volumes.
        # This is cannot detect crossover misaligns and other bad practices.
        if int(num_pp / num_lp) > 1:
            if not int(num_pp / num_pv) == num_lp:
                msgtxt.append("LV Mirrors are misaligned between physical volumes(!)")
                state = max(state, 1)

        # If it's not the boot volume I suspect it should be open.
        # This may need to be changed for some scenarios
        if lvtype != "boot":
            if activation != "open":  # and activation != target_activation:
                msgtxt.append("LV is not opened(!)")
                state = max(state, 1)

        # Detect any, not just mirrored, volumes, that have stale PPs.
        # This means either a disk write failure causing a mirror to go stale
        # or some kind of split mirror backup.
        if mirror != "syncd":
            msgtxt.append("LV is not in sync state(!!)")
            state = max(state, 2)

        if state == 0:
            msgtxt_str = "LV is open/syncd"
        else:
            msgtxt_str = ", ".join(msgtxt)
        return state, msgtxt_str

    return (3, "no such volume found")


check_info["aix_lvm"] = LegacyCheckDefinition(
    service_name="Logical Volume %s",
    # "group"              : "",
    # "default_levels_variable" : "services_default_levels",
    # first check we have a vendor mib from W&T, then check for the model in their MIB.,
    discovery_function=inventory_aix_lvm,
    check_function=check_aix_lvm,
)
