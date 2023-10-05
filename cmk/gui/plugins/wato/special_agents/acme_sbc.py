#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.utils.rulesets.definition import RuleGroup

from cmk.gui.i18n import _
from cmk.gui.plugins.wato.utils import HostRulespec, rulespec_registry
from cmk.gui.valuespec import FixedValue
from cmk.gui.wato import RulespecGroupDatasourceProgramsHardware
from cmk.gui.watolib.rulespecs import Rulespec


def _factory_default_special_agents_acme_sbc():
    # No default, do not use setting if no rule matches
    return Rulespec.FACTORY_DEFAULT_UNUSED


def _valuespec_special_agents_acme_sbc():
    return FixedValue(
        value={},
        title=_("ACME Session Border Controller"),
        help=_(
            "This rule activates an agent which connects "
            "to an ACME Session Border Controller (SBC). This agent uses SSH, so "
            "you have to exchange an SSH key to make a passwordless connect possible."
        ),
        totext=_("Connect to ACME SBC"),
    )


rulespec_registry.register(
    HostRulespec(
        factory_default=_factory_default_special_agents_acme_sbc(),
        group=RulespecGroupDatasourceProgramsHardware,
        name=RuleGroup.SpecialAgents("acme_sbc"),
        valuespec=_valuespec_special_agents_acme_sbc,
    )
)
