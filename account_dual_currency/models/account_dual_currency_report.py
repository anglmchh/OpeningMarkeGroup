# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.tools import format_date
from itertools import groupby
from collections import defaultdict

MAX_NAME_LENGTH = 50


class DualCurrencyReportCustomHandler(models.AbstractModel):
    _name = 'account.dual_currency.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Assets Report Custom Handler'

    def _get_custom_display_config(self):
        print('account.dual_currency.report.handler')
        return {
            'components': {
                'AccountReportFilters': 'account_dual_currency.DualCurrencyFilters',
            }
        }

