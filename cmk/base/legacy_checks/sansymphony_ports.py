#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# <<<sansymphony_ports>>>
# shdesolssy01_FE1 FibreChannel True
# Server_FC_Port_2 FibreChannel True
# Server_FC_Port_3 FibreChannel False
# Server_FC_Port_4 FibreChannel True
# Server_iSCSI_Port_1 iSCSI True
# Microsoft_iSCSI-Initiator iSCSI True


from cmk.base.check_api import LegacyCheckDefinition
from cmk.base.config import check_info


def inventory_sansymphony_ports(info):
    for portname, _porttype, portstatus in info:
        if portstatus == "True":
            yield portname, None


def check_sansymphony_ports(item, _no_params, info):
    for portname, porttype, portstatus in info:
        if portname == item:
            if portstatus == "True":
                return 0, f"{porttype} Port {portname} is up"
            return 2, f"{porttype} Port {portname} is down"
    return None


check_info["sansymphony_ports"] = LegacyCheckDefinition(
    service_name="sansymphony Port %s",
    discovery_function=inventory_sansymphony_ports,
    check_function=check_sansymphony_ports,
)
