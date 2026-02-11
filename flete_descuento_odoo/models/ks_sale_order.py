# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
from odoo.exceptions import UserError, ValidationError
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    groupby,
    index_exists,
    is_html_empty,
)
_logger = logging.getLogger(__name__)

class KsGlobalTaxSales(models.Model):
    _inherit = "sale.order"

    ks_global_tax_rate = fields.Float(string="Flete (%):", readonly=True,
                                      states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    ks_amount_global_tax = fields.Monetary(string='Flete', readonly=True, compute='_amount_all',
                                           tracking=True, store=True)
    ks_enable_tax = fields.Boolean(compute='ks_verify_tax')

    @api.depends('company_id.ks_enable_tax')
    def ks_verify_tax(self):
        for rec in self:
            rec.ks_enable_tax = rec.company_id.ks_enable_tax

    @api.depends('order_line.price_total', 'ks_global_tax_rate')
    def _amount_all(self):
        for rec in self:
            ks_res = super(KsGlobalTaxSales, rec)
            if 'ks_amount_discount' in rec:
                rec.ks_calculate_discount()
            rec.ks_calculate_tax()
        return ks_res


    def _create_invoices(self, grouped=False, final=False, date=False):
        invoices = super(KsGlobalTaxSales, self)._create_invoices(grouped=grouped, final=final, date=date)
        for invoice in invoices:
            tDiscount = 0.0
            for line in invoice.invoice_line_ids:
                #line.discount_line = (line.price_unit_usd - line.price_unit_with_discount) * line.quantity
                dDiscount = line.discount
                tDiscount += dDiscount
                line.discount_line = dDiscount
                line.discount = 0.0
            if tDiscount > 0.0:
                invoice.type_invoice_discount = "linea"
        return invoices

    def _prepare_invoice(self):
        for rec in self:
            xrate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', rec.currency_id.id),
                    ('name', '<=', fields.Date.today())
                ], limit=1, order='name desc').rate
            rate = 1 / xrate
            rec.currency_rate = rate
            _logger.warning(f"steve Global Tax Rate: {rec.ks_global_tax_rate}, Global Tax Amount: {rec.ks_amount_global_tax}, Exchange Rate: {rate}")
            ks_res = super(KsGlobalTaxSales, rec)._prepare_invoice()
            ks_res['ks_global_tax_rate'] = rec.ks_global_tax_rate
            ks_res['ks_amount_global_tax'] = rec.ks_amount_global_tax
            ks_res['tax_today'] = rate
            for line in ks_res['invoice_line_ids']:
                line['discount'] = 0.0
                line['discount_line'] = (rec.price_unit-rec.price_reduce_taxexcl)*line['quantity']
        return ks_res


    def ks_calculate_tax(self):
        for rec in self:
            if rec.ks_global_tax_rate != 0.0:
                rec.ks_amount_global_tax = ((rec.amount_untaxed + rec.amount_tax) * rec.ks_global_tax_rate) / 100
            else:
                rec.ks_amount_global_tax = 0.0

            rec.amount_total = rec.ks_amount_global_tax + rec.amount_untaxed + rec.amount_tax

    @api.constrains('ks_global_tax_rate')
    def ks_check_tax_value(self):
        if self.ks_global_tax_rate > 100 or self.ks_global_tax_rate < 0:
            raise ValidationError('You cannot enter percentage value greater than 100 or less than 0.')

    def _compute_tax_totals(self):
        res = super(KsGlobalTaxSales, self)._compute_tax_totals()
        self.tax_totals['formatted_amount_total'] = formatLang(self.env, self.amount_total,currency_obj=self.currency_id)
        self.tax_totals['amount_total'] = self.amount_total
        self.tax_totals['ks_tax_amount']=formatLang(self.env, self.ks_amount_global_tax,currency_obj=self.currency_id)


class KsSaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _create_invoice(self, order, so_line, amount):
        invoice = super(KsSaleAdvancePaymentInv, self)._create_invoice(order, so_line, amount)
        if invoice:
            invoice['ks_global_tax_rate'] = order.ks_global_tax_rate
            invoice['ks_amount_global_tax'] = order.ks_amount_global_tax
        return invoice


class KsGlobalTaxInvoice(models.Model):
    _inherit = "account.move"


    # @api.depends_context('lang')
    # @api.depends(
    #     'invoice_line_ids.currency_rate',
    #     'invoice_line_ids.tax_base_amount',
    #     'invoice_line_ids.tax_line_id',
    #     'invoice_line_ids.price_total',
    #     'invoice_line_ids.price_subtotal',
    #     'invoice_payment_term_id',
    #     'partner_id',
    #     'currency_id',
    # )
    # def _compute_tax_totals(self):
    #     super()._compute_tax_totals()
    #     for move in self:
    #         inc_total = move.invoice_discount 
    #         if move.is_invoice(include_receipts=True) and move.tax_totals:
    #             if not float_is_zero(inc_total, precision_rounding=move.currency_id.rounding):
    #                 tax_totals = move.tax_totals
    #                 if not  any(move.invoice_line_ids.tax_ids):
    #                     tax_totals['amount_untaxed'] -= inc_total
    #                     tax_totals['formatted_amount_untaxed'] = formatLang(self.env, tax_totals['amount_untaxed'] - inc_total , currency_obj=move.currency_id)
    #                 tax_totals['amount_total'] -= inc_total
    #                 tax_totals['formatted_amount_total'] = formatLang(self.env, tax_totals['amount_total'] - inc_total , currency_obj=move.currency_id)
    #                 inc_group = {
    #                     'tax_group_name': 'Descuento',
    #                     'tax_group_amount': -inc_total,
    #                     'tax_group_base_amount': sum(move.invoice_line_ids.mapped('price_subtotal')),
    #                     'formatted_tax_group_amount': formatLang(self.env, -inc_total, currency_obj=move.currency_id),
    #                     'formatted_tax_group_base_amount': formatLang(self.env, sum(move.invoice_line_ids.mapped('price_subtotal')), currency_obj=move.currency_id),
    #                     'tax_group_id': 'discount', 
    #                 }

    #                 if 'subtotals' in tax_totals['groups_by_subtotal']:
    #                     tax_totals['groups_by_subtotal']['subtotals'].append(inc_group)
    #                 else:
    #                     first_key = next(iter(tax_totals['groups_by_subtotal']), 'Untaxed Amount')
    #                     tax_totals['groups_by_subtotal'][first_key].append(inc_group)
    #                 move.tax_totals = tax_totals
