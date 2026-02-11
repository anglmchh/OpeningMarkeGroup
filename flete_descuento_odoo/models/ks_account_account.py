from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class Company(models.Model):
    _inherit = "res.company"

    ks_enable_tax = fields.Boolean(string="Activar Flete")
    ks_sales_tax_account = fields.Many2one('account.account', string="Cuenta flete ventas")
    ks_purchase_tax_account = fields.Many2one('account.account', string="Cuenta flete Compras")
    sales_discount_account = fields.Many2one('account.account', string="Cuenta Descuento ventas")
    purchase_discount_account = fields.Many2one('account.account', string="Cuenta Descuento Compras")
    ks_second_currency = fields.Many2one('res.currency', string="Segunda moneda")


class KsResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ks_enable_tax = fields.Boolean(string="Activate Universal Tax", related='company_id.ks_enable_tax', readonly=False)
    ks_sales_tax_account = fields.Many2one('account.account', string="Sales Tax Account", related='company_id.ks_sales_tax_account', readonly=False)
    ks_purchase_tax_account = fields.Many2one('account.account', string="Purchase Tax Account", related='company_id.ks_purchase_tax_account', readonly=False)
    ks_second_currency = fields.Many2one('res.currency', string="Segunda moneda", related='company_id.ks_second_currency', readonly=False)
    sales_discount_account = fields.Many2one('account.account', related='company_id.sales_discount_account', string="Sales Tax Account", readonly=False)
    purchase_discount_account = fields.Many2one('account.account', related='company_id.purchase_discount_account',string="Purchase Tax Account", readonly=False)