#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


import json

from cmk.base.check_api import check_levels, LegacyCheckDefinition
from cmk.base.config import check_info
from cmk.base.plugins.agent_based.agent_based_api.v1 import get_value_store

ERROR_DETAILS = {
    "query error": "does not produce a valid result",
    "unsupported query": "produces more than one result (only one allowed)",
    "no value": "returns no value",
}


def parse_prometheus_custom(string_table):
    parsed = {}
    for line in string_table:
        try:
            prometheus_data = json.loads(line[0])
        except ValueError:
            continue
        parsed.update(prometheus_data)
    return parsed


def _check_for_invalid_result(metric_details, promql_expression):
    """Produces the output including service status and infotext for a invalid/failed
       PromQL query (and therefore service metric)

       This function also verifies if the given PromQL expression previously gave a valid output
       and has now become invalid due to changes on the Prometheus side

    Args:
        metric_details: Dict which contains the information of the metric including an error message
                        in case the PromQL query has failed
        promql_expression: String expression of the failed/invalid PromQL query

    Returns: Empty Tuple in case the query gave a valid output or a tuple containing the status and
             infotext for the service to display

    """
    value_store = get_value_store()
    expression_has_been_valid_before = value_store.get(promql_expression, False)
    expression_is_valid_now = "value" in metric_details

    if expression_is_valid_now:
        # Keep a record of the PromQL expressions which gave a valid result at least once
        value_store[promql_expression] = True
        return ()

    if expression_has_been_valid_before:
        status = 1
        infotext = "previously valid is now invalid"
    else:
        status = 2
        infotext = ERROR_DETAILS[metric_details["invalid_info"]]
    return status, f"PromQL expression ({promql_expression}) {infotext}", []


def _metric_levels(
    metric_label,
    datasource_levels,
    service_levels,
):
    """Retrieve the relevant check levels for the relevant service metric value

    Levels for Prometheus custom can be defined at two WATO places:
        1. In Datasource Programs directly next to the custom service definition
        2. In a separate WATO rule

    The WATO rule always has priority over the Datasource rule.

    Args:
        metric_label:
            The current metric label of the current custom Prometheus service

        datasource_levels:
            The datasource levels for the current service metric value

        service_levels:
            The separate defined WATO levels for the current service metric value

    Returns:
        The matching levels in Checkmk format

    """
    missing_levels = (None, None)
    if service_levels:
        for metric_entry in service_levels:
            if metric_entry["metric_label"] == metric_label:
                metric_levels = metric_entry.get("levels", {})
                return (
                    *metric_levels.get("upper_levels", missing_levels),
                    *metric_levels.get("lower_levels", missing_levels),
                )

    if datasource_levels:
        return (
            *datasource_levels.get("upper_levels", missing_levels),
            *datasource_levels.get("lower_levels", missing_levels),
        )
    return None


def check_prometheus_custom(item, params, parsed):
    if not (data := parsed.get(item)):
        return
    for metric_details in data["service_metrics"]:
        promql_expression = metric_details["promql_query"]
        metric_label = metric_details["label"]

        metric_name = metric_details.get("name")
        if metric_name == "null":
            metric_name = None

        invalid_result = _check_for_invalid_result(metric_details, promql_expression)
        if invalid_result:
            yield invalid_result
            continue

        levels = _metric_levels(
            metric_label,
            metric_details.get("levels"),
            params.get("metric_list"),
        )
        yield check_levels(
            float(metric_details["value"]),
            metric_name,
            levels,
            infoname=metric_label,
        )


def discover_prometheus_custom(section):
    yield from ((item, {}) for item in section)


check_info["prometheus_custom"] = LegacyCheckDefinition(
    parse_function=parse_prometheus_custom,
    service_name="%s",
    discovery_function=discover_prometheus_custom,
    check_function=check_prometheus_custom,
    check_ruleset_name="prometheus_custom",
)
