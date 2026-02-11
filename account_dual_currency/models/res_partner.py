# -*- coding: UTF-8 -*-
from email.policy import default

from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp
import re

class ResPartner(models.Model):
    _inherit = 'res.partner'

    currency_id_dif = fields.Many2one('res.currency', string='Moneda $', default=lambda self: self.env.company.currency_id_dif.id)

    total_due = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice', currency_field='currency_id_dif')
    total_overdue = fields.Monetary(
        compute='_compute_total_due',
        groups='account.group_account_readonly,account.group_account_invoice', currency_field='currency_id_dif')

    @api.depends('unreconciled_aml_ids', 'followup_next_action_date')
    @api.depends_context('company', 'allowed_company_ids')
    def _compute_total_due(self):
        today = fields.Date.context_today(self)
        for partner in self:
            total_overdue = 0
            total_due = 0
            for aml in partner.unreconciled_aml_ids:
                is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
                if self.env.company in aml.company_id.parent_ids and not aml.blocked:
                    total_due += aml.amount_residual_usd
                    if is_overdue:
                        total_overdue += aml.amount_residual_usd
            partner.total_due = total_due
            partner.total_overdue = total_overdue