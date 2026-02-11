from odoo import models, fields, api, _
from odoo.exceptions import UserError


from odoo import models, api


class AccountMoveFixTax(models.Model):
    _inherit = 'account.move'

    @api.model
    def action_fix_missing_tax_today(self):
        Company = self.env.company
        CurrencyDif = Company.currency_id_dif

        # Buscar asientos con tasa 0, None o 1
        moves = self.search([
            ('state', '=', 'posted'),
            ('tax_today', 'in', [0.0, 1.0, False]),
            '|', ('invoice_date', '!=', False), ('date', '!=', False)
        ])

        for move in moves:
            date = move.invoice_date or move.date
            if not date:
                continue

            rate_dict = CurrencyDif._get_rates(Company, date)
            if not rate_dict:
                continue

            new_rate = 1 / rate_dict.get(CurrencyDif.id, 1.0)
            if new_rate in [0.0, 1.0]:
                continue  # sigue siendo incorrecta, evitar asignarla

            move.tax_today = new_rate

            # Recalcular líneas contables
            for line in move.line_ids:
                debit_usd = (line.debit / new_rate) if line.debit else 0.0
                credit_usd = (line.credit / new_rate) if line.credit else 0.0
                line.with_context(check_move_validity=False).write({
                    'debit_usd': debit_usd,
                    'credit_usd': credit_usd,
                })

            # Recalcular totales duales
            move._amount_all_usd()
            move._compute_amount()