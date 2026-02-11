from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):
        self.ensure_one()

        account = (
            self.product_id.property_account_expense_id or
            self.product_id.categ_id.property_account_expense_categ_id
        )

        company = self.order_id.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        date = self.order_id.date_order or fields.Date.today()

        price_unit = self.price_unit
        quantity = self.qty_to_invoice
        amount = price_unit * quantity

        # Conversión si aplica
        if currency and currency != company.currency_id:
            amount_converted = currency._convert(
                amount,
                company.currency_id,
                company,
                date,
            )
        else:
            amount_converted = amount

        return {
            'name': self.name,
            'product_id': self.product_id.id,
            'price_unit': price_unit,
            'quantity': quantity,
            'product_uom_id': self.product_uom.id,
            'tax_ids': [(6, 0, self.taxes_id.ids)],
            'purchase_line_id': self.id,
            'display_type': self.display_type or None,
            'account_id': account.id if account else False,
            'balance': amount_converted,
        }
