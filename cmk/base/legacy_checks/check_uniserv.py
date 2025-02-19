#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.base.config import active_check_info


def check_uniserv_arguments(params):
    args = ["$HOSTADDRESS$", params["port"], params["service"]]

    if isinstance(params["job"], tuple):
        job = params["job"][0]
    else:
        job = params["job"]
    if job == "version":
        args.append("VERSION")
    else:
        address = params["job"][1]
        args.append("ADDRESS")
        args.append(address["street"])
        args.append(address["street_no"])
        args.append(address["city"])
        args.append(address["search_regex"])

    return args


def check_uniserv_desc(params):
    job = params["job"]
    if isinstance(job, tuple):
        job = job[0]

    if job == "version":
        return "Uniserv %s Version" % params["service"]
    return "Uniserv {} Address {} ".format(params["service"], params["job"][1]["city"])


active_check_info["uniserv"] = {
    "command_line": "check_uniserv $ARG1$",
    "argument_function": check_uniserv_arguments,
    "service_description": check_uniserv_desc,
}
