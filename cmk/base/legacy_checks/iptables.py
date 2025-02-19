#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# Example output from agent:
# <<<iptables>>>
# -A INPUT -j RH-Firewall-1-INPUT
# -A FORWARD -j RH-Firewall-1-INPUT
# -A OUTPUT -d 10.139.7.11/32 -j REJECT --reject-with icmp-port-unreachable
# -A RH-Firewall-1-INPUT -i lo -j ACCEPT
# -A RH-Firewall-1-INPUT -p icmp -m icmp --icmp-type any -j ACCEPT
# -A RH-Firewall-1-INPUT -p esp -j ACCEPT
# -A RH-Firewall-1-INPUT -p ah -j ACCEPT
# -A RH-Firewall-1-INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 4000 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 80 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 443 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 29543 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 29043 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 30001 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 30000 -j ACCEPT
# -A RH-Firewall-1-INPUT -d 224.0.0.251/32 -p udp -m udp --dport 5353 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 58002 -j ACCEPT
# -A RH-Firewall-1-INPUT -p udp -m udp --dport 58001 -j ACCEPT
# -A RH-Firewall-1-INPUT -p udp -m udp --dport 631 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 631 -j ACCEPT
# -A RH-Firewall-1-INPUT -p tcp -m state --state NEW -m tcp --dport 6556 -j ACCEPT
# -A RH-Firewall-1-INPUT -p udp -m udp --dport 6556 -j ACCEPT
# -A RH-Firewall-1-INPUT -s 89.254.0.0/16 -p tcp -m state --state NEW -m tcp --dport 252 -j ACCEPT
# -A RH-Firewall-1-INPUT -s 89.254.0.0/16 -p tcp -m state --state NEW -m tcp --dport 7070 -j ACCEPT
# -A RH-Firewall-1-INPUT -j REJECT --reject-with icmp-host-prohibited
# COMMIT


import difflib
import hashlib

from cmk.base.check_api import LegacyCheckDefinition
from cmk.base.config import check_info
from cmk.base.plugins.agent_based.agent_based_api.v1 import get_value_store, IgnoreResultsError


def iptables_hash(config):
    return hashlib.sha256(config.encode("utf-8")).hexdigest()


def parse_iptables(string_table):
    config_lines = [" ".join(sublist) for sublist in string_table]
    config = "\n".join(config_lines)
    return config


def inventory_iptables(parsed):
    return [(None, {"config_hash": iptables_hash(parsed)})]


def check_iptables(_no_item, params, parsed):
    value_store = get_value_store()
    item_state = value_store.get("iptables.config")

    if not item_state:
        value_store["iptables.config"] = {"config": parsed, "hash": iptables_hash(parsed)}
        raise IgnoreResultsError(
            "Initial configuration has been saved. The next check interval will contain a valid state."
        )

    initial_config_hash = params["config_hash"]
    new_config_hash = iptables_hash(parsed)

    if initial_config_hash == new_config_hash:
        if initial_config_hash != item_state.get("hash"):
            value_store["iptables.config"] = {"config": parsed, "hash": new_config_hash}
            return 0, "accepted new filters after service rediscovery / reboot"
        return 0, "no changes in filters table detected"

    reference_config = item_state["config"].splitlines()
    actual_config = parsed.splitlines()
    diff = difflib.context_diff(
        reference_config, actual_config, fromfile="before", tofile="after", lineterm=""
    )
    diff_output = "\n".join(diff)

    return 2, "\r\n".join(["changes in filters table detected", diff_output])


check_info["iptables"] = LegacyCheckDefinition(
    parse_function=parse_iptables,
    service_name="Iptables",
    discovery_function=inventory_iptables,
    check_function=check_iptables,
    check_default_parameters={},
)
