from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging
from pprint import pprint
import sys
    
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    discrepancy_threshold = fields.Many2one('account.move.currency')
    discrepancy = fields.Float('Discrepancia', help="Umbral para detectar discrepancias.")
    move_is_error = fields.Boolean('Move no currency')
    def _adjust_total_tax(self):
        for rec in self:
            base_amount = 0
            amount = 0
            rec.ks_amount_global_tax = 0.0
            rec.invoice_discount = 0.0
            total_untaxed = total_untaxed_currency = 0.0
            total_tax = total_tax_currency = 0.0
            total = total_currency = 0.0
            total_to_pay = total_residual = total_residual_currency = 0.0
            sign = 1 if rec.move_type == 'entry' or rec.is_outbound() else -1
            if rec.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']:
                base_amount = rec.amount_untaxed
                if rec.enable_invoice_discount == 'percent':
                    if rec.type_invoice_discount == 'global' and rec.invoice_discount_percent != 0:
                        rec.invoice_discount = (base_amount * rec.invoice_discount_percent) / 100
                    elif rec.type_invoice_discount == 'linea':
                        discount_amount = sum((line.price_unit - line.price_unit_with_discount) * line.quantity for line in rec.invoice_line_ids)
                        rec.invoice_discount = discount_amount
                amount = rec.amount_untaxed - rec.invoice_discount
                rec.write({'ks_amount_global_tax' : (rec.amount_untaxed * rec.ks_global_tax_rate) / 100})
                for line in rec.line_ids.filtered(lambda line: line.display_type != 'cogs'):
                    if line.display_type not in ('product','cogs'):
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                    elif line.account_id.account_type in ('asset_receivable', 'liability_payable'):
                        # Residual amount.
                        total_to_pay += line.balance
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                    rec.write({'amount_total':rec.discrepancy, 
                                'amount_untaxed': sign * total_untaxed_currency, 
                                'amount_residual': -sign * (total_residual_currency),
                                'amount_residual_signed': total_residual,
                                'amount_untaxed_signed': -total_untaxed})

    def _compute_totals_and_update(self):
        pass
        # for move in self:
        #     total_untaxed = total_untaxed_currency = 0.0
        #     total_tax = total_tax_currency = 0.0
        #     total = total_currency = 0.0
        #     total_to_pay = total_residual = total_residual_currency = 0.0
        #     currencies = move.line_ids.mapped('currency_id')

        #     for line in move.line_ids.filtered(lambda line: line.is_anglo_saxon_line == False):
        #         if move._payment_state_matters():
        #             # === Invoices ===

        #             if not line.exclude_from_invoice_tab:
        #                 # Untaxed amount.
        #                 total_untaxed += line.balance
        #                 total_untaxed_currency += line.amount_currency
        #             elif line.tax_line_id:
        #                 # Tax amount.
        #                 total_tax += line.balance
        #                 total_tax_currency += line.amount_currency
        #             elif line.account_id.user_type_id.type in ('receivable', 'payable'):
        #                 # Residual amount.
        #                 total_to_pay += line.balance
        #                 total_residual += line.amount_residual
        #                 total_residual_currency += line.amount_residual_currency
        #             total += line.balance
        #             total_currency += line.amount_currency
        #         else:
        #             # === Miscellaneous journal entry ===
        #             if line.debit:
        #                 total += line.balance
        #                 total_currency += line.amount_currency

        #     # Determinar el signo para los totales
        #     sign = 1 if move.move_type == 'entry' or move.is_outbound() else -1

        #     # Preparar los valores a actualizar
        #     update_vals = {
        #         'amount_untaxed': sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed),
        #         'amount_tax': sign * (total_tax_currency if len(currencies) == 1 else total_tax),
        #         'amount_total': sign * (total_currency if len(currencies) == 1 else total),
        #         'amount_residual': -sign * (total_residual_currency if len(currencies) == 1 else total_residual),
        #         'amount_untaxed_signed': -total_untaxed,
        #         'amount_tax_signed': -total_tax,
        #         'amount_total_signed': abs(total) if move.move_type == 'entry' else -total,
        #         'amount_residual_signed': total_residual,
        #         'amount_total_in_currency_signed': abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total),
        #     }

        #     # Realizar la actualización
        #     move.write(update_vals)
class AccountMove(models.Model):
    _inherit = "account.move.line"

    move_is_error = fields.Boolean('Move no currency')

    # @api.onchange('currency_id','move_id.trm_invoice')
    # def _onchange_currency(self):
    #     for line in self:
    #         company = line.move_id.company_id

    #         if line.move_id.is_invoice(include_receipts=True):
    #             line._onchange_price_subtotal()
    #         if not line.move_id.reversed_entry_id:
    #             balance = line.currency_id._convert(line.amount_currency, company.currency_id, company, line.move_id.date or fields.Date.context_today(line))
    #             line.debit = balance if balance > 0.0 else 0.0
    #             line.credit = -balance if balance < 0.0 else 0.0
    #         if line.move_id.reversed_entry_id and line.move_id.trm_invoice:
    #             balance = line.currency_id._convert(line.amount_currency, company.currency_id, company, line.move_id.reversed_entry_id.date or fields.Date.context_today(line))
    #             line.debit = balance if balance > 0.0 else 0.0
    #            line.credit = -balance if balance < 0.0 else 0.0

class AccountMove(models.Model):
    _inherit = "account.move.line"
    _sql_constraints = [
        ('check_amount_currency_balance_sign', 'unique(1=1)', 'The phone unique among companies!')
    ]
 
class AccountMoveCurrency(models.Model):
    _name = 'account.move.currency'
    _description = "Ajuste de moneda"

    bill = fields.Boolean('Facturas de Compra')
    sale = fields.Boolean('Facturas de ventas')
    date_from = fields.Date("Fecha Inicio", required=True)
    date_to = fields.Date("Fecha Fin", required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company.id,
        required=False,
        string="Company",
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('progress', 'Progreso'),
        ('confirmed', 'Confirmado'),
        ('cancel', 'Cancelado'),
    ],
        readonly=True,
        default='draft',
        copy=False,
        string="Estado",
        index=True,
    )
    discrepancy_threshold = fields.Float('Umbral de discrepancia', default=2.0, help="Umbral para detectar discrepancias.")
    account_move = fields.One2many('account.move', 'discrepancy_threshold', string='Moviento Contables', readonly=True)


    def button_compute(self):
        self._get_invoices_with_discrepancies()
        self.write({'state':'progress'})
    
    def button_draft(self):
        for rec in self:
            rec.account_move.write({'discrepancy_threshold':False})
        self.write({'state':'draft'})

    def button_exec(self):
        context = self.env.context.copy()
        context.update({
            'check_move_validity': False,
            'tracking_disable': True,
            'force_delete': True
        })
        for rec in self:
            for move in rec.account_move:
                self.env.cr.execute("UPDATE account_move SET state = 'draft' WHERE id IN %s", (tuple(rec.account_move.ids),))
                move.line_ids.write({'move_is_error':True})
                move.with_context(context)._onchange_currency()
                move.with_context(context)._compute_amount()
                move.with_context(context)._recompute_universal_tax_lines() 
                move.with_context(context)._recompute_tax_lines(recompute_tax_base_amount=True, tax_rep_lines_to_recompute=None)
                self.env.cr.execute("UPDATE account_move SET state = 'posted' WHERE id IN %s", (tuple(rec.account_move.ids),))
            for line in rec.account_move.line_ids:
                line.with_context(context)._set_price_and_tax_after_fpos()
        self.write({'state':'confirmed'})

    def _get_invoices_with_discrepancies(self):
        for rec in self:
            rec.account_move.write({'discrepancy_threshold':False})
            domain = [('state', '=', 'posted'), ('payment_state','=','not_paid'),
                ('discrepancy_threshold', '=', False),
                ('company_id','=',rec.company_id.id),
                ('date','>=',rec.date_from),
                ('date','<=',rec.date_to),]
            if rec.bill:
                domain.append(('move_type', 'in', ('in_invoice', 'in_refund')))
            if rec.sale:
                domain.append(('move_type', 'in', ('out_invoice', 'out_refund')))

            Invoice = self.env['account.move']
            invoices = Invoice.search(domain)

            updates = []  # Lista para acumular las actualizaciones

            for inv in invoices:
                subtotal = sum(line.balance for line in inv.invoice_line_ids)
                if inv.currency_id != rec.company_id.currency_id:
                    other_lines = inv.line_ids.filtered(lambda line: line.account_id.account_type not in ('asset_receivable', 'liability_payable'))
                    terms_lines = inv.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable') and not line.display_type == 'cogs')
                    total_balance = sum(terms_lines.mapped('amount_currency'))
                    discrepancy_value = abs(subtotal - inv.amount_total)
                    if abs(total_balance) != abs(inv.amount_total):
                        # Agrega los cambios necesarios en la lista de actualizaciones
                        updates.append((inv.id, {
                            'discrepancy_threshold': rec.id,
                            'discrepancy': total_balance
                        }))
                else:
                    pass
            # Realiza la actualización en lote si hay facturas para actualizar
            if updates:
                for invoice_id, update_data in updates:
                    Invoice.browse(invoice_id).write(update_data)

        return True