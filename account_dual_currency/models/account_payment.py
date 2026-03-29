# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.payment'

    tax_today = fields.Float(string="Tasa BCV", default=lambda self: self._get_default_tasa(), digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency",
                                      string="Divisa de Referencia",
                                      default=lambda self: self.env.company.currency_id_dif )
    currency_id_company = fields.Many2one("res.currency",
                                      string="Divisa compañia",
                                      default=lambda self: self.env.company.currency_id )
    amount_local = fields.Monetary(string="Importe local", currency_field='currency_id_company')
    amount_ref = fields.Monetary(string="Importe referencia", currency_field='currency_id_dif' )
    currency_equal = fields.Boolean(compute="_currency_equal")
    move_id_dif = fields.Many2one(
        'account.move', 'Asiento contable diferencia',  # required=True,
        readonly=True,
        help="Asiento contable de diferencia en tipo de cambio")

    currency_id_name = fields.Char(related="currency_id.name")
    journal_igtf_id = fields.Many2one('account.journal', string='Diario IGTF', check_company=True)
    aplicar_igtf_divisa = fields.Boolean(string="Aplicar IGTF")
    igtf_divisa_porcentage = fields.Float('% IGTF', related='company_id.igtf_divisa_porcentage')

    mount_igtf = fields.Monetary(currency_field='currency_id', string='Importe IGTF', readonly=True,
                                 digits='Dual_Currency')

    amount_total_pagar = fields.Monetary(currency_field='currency_id', string="Total Pagar(Importe + IGTF):",
                                         readonly=True)

    # ✅ CAMPO CORRECTO Y ESTANDARIZADO
    move_igtf_id = fields.Many2one(
        'account.move',
        string='Asiento IGTF', # Se renombra el string para mayor claridad
        readonly=True,
        copy=False
    )

    def _get_default_tasa(self):
        return self.env.company.currency_id_dif.rate

    @api.depends('currency_id_dif', 'currency_id', 'amount', 'tax_today')
    def _currency_equal(self):
        for rec in self:
            currency_equal = rec.currency_id_company != rec.currency_id
            if currency_equal:
                rec.amount_local = rec.amount * rec.tax_today
                rec.amount_ref = rec.amount
            else:
                rec.amount_local = rec.amount
                rec.amount_ref = (rec.amount / rec.tax_today) if rec.amount > 0 and rec.tax_today > 0 else 0
            rec.currency_equal = currency_equal

    def action_post(self):
        res = super().action_post()
        for payment in self:
            # La condición ahora busca 'move_igtf_id'
            if payment.aplicar_igtf and payment.mount_igtf > 0 and not payment.move_igtf_id:
                payment._create_igtf_move()
        return res


    def action_cancel(self):
        # La lógica ahora busca en 'move_igtf_id'
        moves_to_cancel = self.mapped('move_igtf_id').filtered(lambda m: m.state == 'posted')
        if moves_to_cancel:
            moves_to_cancel.button_cancel()
        return super().action_cancel()

    def action_draft(self):
        res = super().action_draft()
        # La lógica ahora busca en 'move_igtf_id'
        moves_to_draft = self.mapped('move_igtf_id').filtered(lambda m: m.state == 'cancel')
        if moves_to_draft:
            moves_to_draft.button_draft()
        return res


    def _create_igtf_move(self):
        """
        NUEVO MÉTODO: Genera el asiento contable del IGTF.
        """
        self.ensure_one()
        _logger.info(f"Iniciando creación de asiento IGTF para el pago {self.name} por un monto de {self.mount_igtf}")
        
        # 1. Validaciones cruciales
        journal = self.journal_igtf_id or self.journal_id
        if not journal:
            raise UserError(_("Debe seleccionar un 'Diario IGTF' o tener un diario en el pago para registrar la transacción."))

        # 2. Determinar cuentas desde la configuración de la compañía (mejor práctica)
        # La cuenta de gasto/pasivo del IGTF
        if self.payment_type == 'inbound': # Es un cobro a un cliente
            expense_account = self.company_id.account_debit_wh_igtf_id
            if not expense_account:
                raise UserError(_("Debe configurar la 'Cuenta de Gasto por IGTF' en los ajustes de contabilidad para cobros."))
        else: # Es un pago a un proveedor ('outbound')
            expense_account = self.company_id.account_credit_wh_igtf_id
            if not expense_account:
                raise UserError(_("Debe configurar la 'Cuenta de Gasto por IGTF' en los ajustes de contabilidad para pagos."))

        # La cuenta de contrapartida (banco/caja desde donde sale el dinero del IGTF)
        # Usamos la cuenta de Pagos Pendientes (Outstanding Payments) de la compañía
        bank_account = self.company_id.account_journal_payment_credit_account_id
        if not bank_account:
            raise UserError(_("La compañía no tiene una 'Cuenta de Pagos Pendientes' configurada."))

        # 3. Preparar los valores del asiento contable
        move_vals = {
            'ref': f'IGTF del Pago {self.name}',
            'date': self.date,
            'journal_id': journal.id,
            'move_type': 'entry',
            'line_ids': [
                # Línea del Gasto IGTF
                (0, 0, {
                    'name': 'Gasto por Comisión IGTF',
                    'account_id': expense_account.id,
                    'debit': self.mount_igtf, # Siempre al DEBE, es un gasto
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                }),
                # Línea de la contrapartida (Salida de Banco/Caja)
                (0, 0, {
                    'name': 'Comisión Bancaria IGTF',
                    'account_id': bank_account.id,
                    'debit': 0.0,
                    'credit': self.mount_igtf, # Siempre al HABER, es una salida de dinero
                    'partner_id': self.partner_id.id,
                }),
            ],
        }
        
        # 4. Crear, publicar y enlazar el asiento
        igtf_move = self.env['account.move'].create(move_vals)
        igtf_move._post()
        
        self.write({'move_igtf_id': igtf_move.id})
        _logger.info(f"Asiento IGTF {igtf_move.name} creado y enlazado exitosamente al pago {self.name}")
        
        return igtf_move

