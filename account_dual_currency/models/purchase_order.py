from odoo import api, fields, models, _
from odoo.exceptions import UserError
from itertools import groupby
from odoo.tools.float_utils import float_is_zero

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_create_invoice(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoice_vals_list = []
        sequence = 10

        for order in self:
            if order.invoice_status != 'to invoice':
                continue

            order = order.with_company(order.company_id)
            pending_section = None
            invoice_vals = order._prepare_invoice()

            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue

                if not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    if pending_section:
                        section_vals = pending_section._prepare_account_move_line()
                        section_vals.update({
                            'sequence': sequence,
                            'display_type': pending_section.display_type or 'line_section',
                        })
                        invoice_vals['invoice_line_ids'].append((0, 0, section_vals))
                        sequence += 1
                        pending_section = None

                    line_vals = line._prepare_account_move_line()
                    line_vals.update({
                        'sequence': sequence,
                        'display_type': line.display_type or None,
                    })
                    invoice_vals['invoice_line_ids'].append((0, 0, line_vals))
                    sequence += 1

            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(_(
                'There is no invoiceable line. If a product has a control policy based on received quantity, '
                'please make sure that a quantity has been received.'
            ))

        # Agrupar por empresa, proveedor y moneda
        new_invoice_vals_list = []
        for grouping_keys, invoices in groupby(
            invoice_vals_list,
            key=lambda x: (x.get('company_id'), x.get('partner_id'), x.get('currency_id'))
        ):
            origins = set()
            payment_refs = set()
            refs = set()
            ref_invoice_vals = None

            for invoice_vals in invoices:
                if not ref_invoice_vals:
                    ref_invoice_vals = invoice_vals
                else:
                    ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']

                origins.add(invoice_vals['invoice_origin'])
                payment_refs.add(invoice_vals['payment_reference'])
                refs.add(invoice_vals['ref'])

            ref_invoice_vals.update({
                'ref': ', '.join(refs)[:2000],
                'invoice_origin': ', '.join(origins),
                'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
            })
            new_invoice_vals_list.append(ref_invoice_vals)

        invoice_vals_list = new_invoice_vals_list

        # Crear las facturas
        moves = self.env['account.move']
        AccountMove = self.env['account.move'].with_context(default_move_type='in_invoice', calcular_dual_currency=False)

        for vals in invoice_vals_list:
            # Obtener fecha (actual o estimada)
            invoice_date = vals.get('invoice_date') or fields.Date.context_today(self)
            company = self.env.company
            currency_from = company.currency_id_dif
            currency_to = company.currency_id

            # Obtener tasa oficial real para esa fecha
            real_rate = self.env['res.currency']._get_conversion_rate(
                from_currency=currency_from,
                to_currency=currency_to,
                company=company,
                date=invoice_date,
            )

            vals['tax_today'] = real_rate
            moves |= AccountMove.with_company(vals['company_id']).create(vals)

        # Cambiar tipo a "refund" si el monto es negativo
        moves.filtered(lambda m: m.currency_id.round(m.amount_total) < 0).action_switch_move_type()

        return self.action_view_invoice(moves)
