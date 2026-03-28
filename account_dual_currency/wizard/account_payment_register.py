# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)
from odoo.tools.float_utils import float_is_zero, float_compare
import datetime

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    amount = fields.Monetary(currency_field='currency_id', store=True, readonly=False)
    tax_today = fields.Float(string="Tasa Actual", digits='Dual_Currency_rate')
    tax_invoice = fields.Float(string="Tasa Factura", digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency",string="Divisa de Referencia")
    currency_id_name = fields.Char(related="currency_id.name")
    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif',string='Adeudado Divisa Ref.', readonly=True, digits='Dual_Currency')
    payment_difference_bs = fields.Monetary(string="Diferencia Bs", currency_field='company_currency_id', digits='Dual_Currency')
    payment_difference_usd = fields.Monetary(string="Diferencia $", currency_field='currency_id_dif',
                                            digits='Dual_Currency')
    # journal_id_dif = fields.Many2one('account.journal', 'Diario de diferencia', store=True,
    #                              domain="[('company_id', '=', company_id)]")
    amount_usd = fields.Monetary(currency_field='currency_id_dif',string='Importe $', readonly=True, digits='Dual_Currency')

    
    # --- ✨ CAMPOS IGTF CORREGIDOS Y MEJORADOS ---
    show_igtf_option = fields.Boolean(
        string="Mostrar Opción IGTF",
        compute='_compute_show_igtf_option',
        help="Campo técnico para mostrar la opción de IGTF solo en pagos en moneda local (VEF)."
    )
    aplicar_igtf = fields.Boolean(
        string="Aplicar Retención IGTF",
        default=False
    )
    igtf_porcentage = fields.Float(
        '% IGTF',
        related='company_id.igtf_divisa_porcentage',
        readonly=True
    )
    journal_igtf_id = fields.Many2one(
        'account.journal',
        string='Diario IGTF',
        domain="[('type', 'in', ('bank', 'cash'))]",
        help="Diario donde se registrará el débito bancario del IGTF."
    )
    mount_igtf = fields.Monetary(
        currency_field='company_currency_id', # Siempre en VEF
        string='Monto IGTF',
        readonly=True,
        compute='_compute_mount_igtf'
    )
    amount_total_pagar = fields.Monetary(
        currency_field='currency_id',
        string="Total a Pagar (Importe + IGTF)",
        readonly=True,
        compute='_compute_mount_igtf'
    )

    # --- NUEVOS CAMPOS SOLO LECTURA ---
    amount_divisa = fields.Monetary(
        string="Importe en Divisa", currency_field='currency_id_dif',
        digits='Dual_Currency', readonly=True, store=True, compute='_compute_dual_expected_diff'
    )
    amount_expected = fields.Monetary(
        string="Importe Esperado", currency_field='currency_id',
        digits='Dual_Currency', readonly=True, store=True, compute='_compute_dual_expected_diff',
        help="Importe en Divisa * Tasa Factura"
    )
    # ✅ --- NUEVO CAMPO MANUAL ---
    amount_expected_manual = fields.Monetary(
        string="Importe Esperado Manual",
        currency_field='company_currency_id',
        digits='Dual_Currency',
        help="Si este campo es mayor a 0, se usará este valor como el importe esperado en lugar del calculado automáticamente."
    )
    amount_diff = fields.Monetary(
        string="Diferencia", currency_field='company_currency_id',
        digits='Dual_Currency', readonly=True, store=True, compute='_compute_dual_expected_diff',
        help="(Importe Esperado) - (Tasa Actual * Importe en Divisa)"
    )

    journal_id_dif = fields.Many2one(
        'account.journal',
        string='Diario Diferencial',
        domain="[('company_id', '=', company_id), ('is_exchange_diff_journal', '=', True)]",
        help="Diario donde se registrará el asiento de diferencia cambiaria."
    )

    is_exchange_diff_journal = fields.Boolean(
        string="Es Diario Diferencial",
        compute='_compute_is_exchange_diff_journal',
        store=False, # No es necesario almacenar en un wizard.
    )


    # --- 💡 LÓGICA MEJORADA ---

    @api.depends('currency_id', 'company_id.currency_id')
    def _compute_show_igtf_option(self):
        """
        El IGTF solo aplica a pagos en la moneda local (VEF).
        Este campo controla la visibilidad de la opción en la vista.
        """
        for wizard in self:
            wizard.show_igtf_option = wizard.currency_id == wizard.company_id.currency_id

    @api.depends('amount', 'aplicar_igtf', 'show_igtf_option')
    def _compute_mount_igtf(self):
        """
        Calcula el monto del IGTF y el total a pagar.
        Se ejecuta solo si la opción está activa y visible.
        """
        for wizard in self:
            if wizard.aplicar_igtf:
                wizard.mount_igtf = wizard.amount * (wizard.igtf_porcentage / 100)
                wizard.amount_total_pagar = wizard.amount + wizard.mount_igtf
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

    @api.depends('journal_id') 
    def _compute_is_exchange_diff_journal(self):
        """Calcula si el diario seleccionado es un diario de diferencial cambiario."""
        for rec in self:
            # Intentamos acceder al campo 'is_exchange_diff_journal' del modelo account.journal.
            # Usamos getattr() para evitar un AttributeError si el campo no se carga por alguna razón.
            rec.is_exchange_diff_journal = bool(
                getattr(rec.journal_id, 'is_exchange_diff_journal', False) or
                getattr(rec.journal_id, 'is_fx_diff_journal', False))

    @api.depends('amount', 'tax_invoice', 'tax_today', 'currency_id', 'currency_id_dif', 'line_ids', 'payment_date', 'amount_expected_manual')
    def _compute_dual_expected_diff(self):
        currency_precision = self.env['decimal.precision'].precision_get('Currency')

        for w in self:
            company = w.company_id
            company_cur = company.currency_id
            ref_cur = w.currency_id_dif or company.currency_id_dif
            pay_cur = w.currency_id
            
            tax_today = float(w.tax_today or 0.0)
            tax_inv = float(w.tax_invoice or tax_today)
            date_ctx = w.payment_date or fields.Date.context_today(w)

            # --- Pagado (en Bs y en USD) (código sin cambios) ---
            if pay_cur == company_cur:
                paid_bs = float(w.amount or 0.0)
                paid_usd = round((paid_bs / tax_today) if tax_today else 0.0, 2)
            elif ref_cur and pay_cur == ref_cur:
                paid_usd = float(w.amount or 0.0)
                paid_bs = round(paid_usd * tax_today, 2)
            else:
                paid_bs = pay_cur._convert(float(w.amount or 0.0), company_cur, company, date_ctx)
                paid_usd = round((paid_bs / tax_today) if tax_today else 0.0, 2)

            # --- Residual USD de las facturas del wizard (código sin cambios) ---
            residual_usd = 0.0
            for inv in w.line_ids.mapped('move_id'):
                if hasattr(inv, 'amount_residual_usd') and inv.amount_residual_usd:
                    residual_usd += float(inv.amount_residual_usd)
                else:
                    residual_usd += round((float(inv.amount_residual or 0.0) / tax_inv) if tax_inv else 0.0, 2)

            used_usd = round(min(paid_usd, residual_usd) if residual_usd else 0.0, 2)

            # --- CÁLCULO DE IMPORTE ESPERADO (Lógica sin cambios) ---
            auto_amount_expected = round(used_usd * tax_inv, 2)
            final_amount_expected = w.amount_expected_manual if w.amount_expected_manual > 0 else auto_amount_expected
                
            # --- CÁLCULO DEL DIFERENCIAL CAMBIARIO (FX) ---
            
            fx_bs = round(paid_bs - final_amount_expected, 2)

            # CRÍTICO: Anular el diferencial (FX) si la tasa de factura es igual a la tasa actual
            if float_compare(tax_inv, tax_today, precision_digits=currency_precision) == 0:
                fx_bs = 0.0 # No hay diferencial cambiario

            # Campos de ayuda en el wizard
            w.amount_divisa = round(ref_cur.round(paid_usd) if ref_cur else paid_usd, 2)
            w.amount_expected = final_amount_expected
            w.amount_diff = fx_bs # Este es el valor que refleja la diferencia cambiaria

    @api.onchange("payment_date")
    def onchange_date_change_tax_today(self):
        currency_USD = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        company_currency = self.env.company.currency_id
        self.tax_today = company_currency._get_conversion_rate(currency_USD, company_currency, self.env.company, self.payment_date)

    # @api.depends('currency_id')
    # def _get_default_igtf(self):
    #     if self.currency_id == self.company_id.currency_id:
    #         return False
    #     else:
    #         return self.company_id.aplicar_igtf
    # @api.onchange('aplicar_igtf')
    # def _mount_igtf(self):
    #     for wizard in self:
    #         if wizard.aplicar_igtf:
    #             if wizard.currency_id.name == 'VEF':
    #                 wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
    #                 wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
    #             else:
    #                 wizard.mount_igtf = 0
    #                 wizard.amount_total_pagar = wizard.amount
    #         else:
    #             wizard.mount_igtf = 0
    #             wizard.amount_total_pagar = wizard.amount


    @api.onchange('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', "tax_today")
    def _compute_amount(self):
        currency_precision = self.env['decimal.precision'].precision_get('Currency')

        for wizard in self:
            tax_today = float(wizard.tax_today or 0.0)
            tax_invoice = float(wizard.tax_invoice or 0.0)
            
            # CRÍTICO: Compara si las tasas son iguales
            is_tax_equal = float_compare(tax_today, tax_invoice, precision_digits=currency_precision) == 0

            # Determinar el residual a pagar, ya sea en moneda local (VEF) o divisa (USD)
            if wizard.currency_id == wizard.company_id.currency_id:
                # Moneda de Pago = VEF (Compañía)
                residual_to_match = wizard.source_amount 
            else:
                # Moneda de Pago = Divisa (USD u otra)
                residual_to_match = wizard.source_amount_currency
            
            # --- Lógica para anular la diferencia nativa ---
            if is_tax_equal:
                # Si las tasas son iguales, el importe del pago debe ser exactamente el residual 
                # (o el monto parcial que el usuario haya seteado en wizard.amount, si fuera menor).
                # Para anular la diferencia nativa, forzamos el monto al residual total.
                wizard.amount = residual_to_match
            
            # --- Lógica de cálculo normal (si las tasas son diferentes) ---
            elif wizard.source_currency_id == wizard.currency_id:
                wizard.amount = wizard.source_amount

            elif wizard.currency_id == wizard.company_id.currency_id:
                # Pago en VEF para factura en USD.
                wizard.amount = wizard.amount_residual_usd * tax_today
            
            else:
                # Pago en Divisa para factura en VEF.
                wizard.amount = wizard.amount_residual_usd

            # --- Lógica IGTF/Final de VEF (se mantiene para la cadena de onchange) ---
            if wizard.aplicar_igtf:
                if wizard.currency_id.name == wizard.company_id.currency_id_dif.name:
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

            # Nota: La línea "if wizard.currency_id.name == "VEF": wizard.amount = ..." 
            # se elimina porque es redundante o causa errores de redondeo, el caso ya está cubierto arriba.

    @api.depends('amount', 'tax_today', 'tax_invoice', 'currency_id', 'currency_id_dif',
             'company_id', 'payment_type', 'payment_date', 'line_ids')
    def _compute_payment_difference(self):
        # 1) Deja que Odoo compute su payment_difference nativo
        super(AccountPaymentRegister, self)._compute_payment_difference()
        
        currency_precision = self.env['decimal.precision'].precision_get('Currency')

        for w in self:
            tax_today = float(w.tax_today or 0.0)
            tax_invoice = float(w.tax_invoice or 0.0)
            
            # 2. CRÍTICO: Si las tasas son iguales, ANULAR la diferencia nativa
            if float_compare(tax_invoice, tax_today, precision_digits=currency_precision) == 0:
                # Si las tasas son iguales, forzamos la diferencia de pago visible (w.payment_difference) a CERO.
                w.payment_difference = 0.0
                
            # --- El resto del código solo actualiza tus campos informativos ---

            company = w.company_id
            company_cur = company.currency_id
            ref_cur = w.currency_id_dif or company.currency_id_dif
            pay_cur = w.currency_id
            tax_today = float(w.tax_today or 0.0)
            date_ctx = w.payment_date or fields.Date.context_today(w)

            # -- Pagado en Bs (solo para mostrar equivalentes)
            if pay_cur == company_cur:
                paid_bs = float(w.amount or 0.0)
            elif ref_cur and pay_cur == ref_cur:
                paid_bs = float(w.amount or 0.0) * (tax_today or 0.0)
            else:
                paid_bs = pay_cur._convert(float(w.amount or 0.0), company_cur, company, date_ctx)

            # 2) Tus campos informativos
            overpay_bs = company_cur.round(float(w.payment_difference or 0.0))
            overpay_usd = (overpay_bs / tax_today) if tax_today else 0.0

            w.payment_difference_bs = overpay_bs
            w.payment_difference_usd = (ref_cur.round(overpay_usd) if ref_cur else round(overpay_usd, 2))

            # 3) IGTF / total (sin cambios)
            if w.aplicar_igtf and pay_cur and ref_cur and pay_cur.name == ref_cur.name:
                w.mount_igtf = (w.amount or 0.0) * (w.igtf_divisa_porcentage or 0.0) / 100.0
            else:
                w.mount_igtf = 0.0
            w.amount_total_pagar = (w.amount or 0.0) + (w.mount_igtf or 0.0)

    @api.model
    def _get_wizard_values_from_batch(self, batch_result):
        key_values = batch_result['payment_values']
        lines = batch_result['lines']
        company = lines[0].company_id

        # 1. Obtén la fecha de pago (o usa hoy si no está seteada)
        payment_date = self.payment_date or fields.Date.context_today(self)

        # 2. Busca el currency USD y la tasa más reciente válida según fecha y compañía
        usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        tax_today = 1.0
        if usd:
            rate_obj = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd.id),
                ('company_id', '=', company.id),
                ('name', '<=', payment_date),
            ], order='name desc', limit=1)
            if rate_obj:
                tax_today = rate_obj.inverse_company_rate or 1.0

        # 3. tax_invoice sigue siendo la tasa guardada en la factura (si existe)
        tax_invoice = getattr(lines[0].move_id, 'tax_today', 1.0) or 1.0

        currency_id_dif = lines[0].currency_id_dif
        amount_residual_usd = lines[0].move_id.amount_residual_usd
        source_amount = abs(sum(lines.mapped('amount_residual'))) if key_values['currency_id'] == company.currency_id.id else abs(sum(lines.mapped('amount_residual_currency')))
        if key_values['currency_id'] == company.currency_id.id:
            source_amount_currency = source_amount
        else:
            source_amount_currency = abs(sum(lines.mapped('amount_residual_currency')))

        return {
            'company_id': company.id,
            'partner_id': key_values['partner_id'],
            'partner_type': key_values['partner_type'],
            'payment_type': key_values['payment_type'],
            'source_currency_id': key_values['currency_id'],
            'source_amount': source_amount,
            'source_amount_currency': source_amount_currency,
            'tax_today': tax_today,      # <--- Ahora sí, última tasa válida
            'tax_invoice': tax_invoice,  # <--- Tasa guardada en la factura
            'currency_id_dif': currency_id_dif.id,
            'amount_residual_usd': amount_residual_usd,
            'aplicar_igtf': self.aplicar_igtf,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        # Determinar tasa correcta según la moneda del pago
        if self.currency_id == self.company_id.currency_id_dif:
            # Pago en USD → usar tasa de la factura
            tasa_aplicada = self.tax_invoice
        else:
            # Pago en VEF u otra moneda → usar tasa actual
            tasa_aplicada = self.tax_today

        payment_vals = {
            'date': self.payment_date,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'partner_type': self.partner_type,
            'ref': self.communication,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'partner_bank_id': self.partner_bank_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'destination_account_id': self.line_ids[0].account_id.id,
            'tax_today': self.tax_today,  # 👈 Condicionado correctamente
            'currency_id_dif': self.currency_id_dif.id,
            'aplicar_igtf': self.aplicar_igtf,
            'journal_igtf_id': self.journal_igtf_id.id,
            'mount_igtf': self.mount_igtf,
            'amount_total_pagar': self.amount_total_pagar,
        }
        return payment_vals

    def _auto_reconcile_payment_dif(self):
        """
        Conciliar automáticamente las líneas AR/AP del pago con las del asiento
        de diferencia cambiaria, siempre que queden exactamente dos líneas
        opuestas y conciliables en la misma cuenta.
        """
        for payment in self:
            if not getattr(payment, 'move_id_dif', False):
                continue

            pay_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )
            dif_lines = payment.move_id_dif.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )

            for account in (pay_lines.account_id | dif_lines.account_id):
                p_acc = pay_lines.filtered(lambda l: l.account_id == account and not l.reconciled)
                d_acc = dif_lines.filtered(lambda l: l.account_id == account and not l.reconciled)
                group = (p_acc + d_acc).filtered(lambda l: not l.reconciled)

                if len(group) == 2 and round(sum(l.balance for l in group), 2) == 0.0:
                    try:
                        group.reconcile()
                        _logger.info(
                            "[AUTO-RECON] Pago %s conciliado con DIF en cuenta %s",
                            payment.id, account.code
                        )
                    except Exception as e:
                        _logger.exception("[AUTO-RECON] Error conciliando Pago %s con DIF: %s", payment.id, e)

    def _create_payments(self):
        _logger.info("[PAY-DBG] === INICIO _create_payments (Versión Final Corregida) ===")

        # 1. Crear el pago base (Super)
        payments = super(AccountPaymentRegister, self.with_context(
            tasa_factura=self.tax_today,
            calcular_dual_currency=True
        ))._create_payments()

        if not payments or not getattr(payments, 'move_id', False):
            _logger.error("[PAY-DBG] No se obtuvo payments.move_id desde super(). Abortando.")
            return payments

        # -------------------------------------------------------------------------
        # 🔍 DETECCIÓN INTELIGENTE DE LA LÍNEA DEL PARTNER
        # -------------------------------------------------------------------------
        # Buscamos la línea que NO es de liquidez (Banco) y que es AR/AP.
        liquidity_account = payments.journal_id.default_account_id
        
        pay_arap_line = payments.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            and l.account_id != liquidity_account # Excluir cuenta de banco del diario
            and l.partner_id == self.partner_id
        )[:1]

        if not pay_arap_line:
            _logger.warning("[PAY-DBG] ⚠️ No se encontró línea AR/AP en el pago. Saltando diferencial.")
            return payments

        # Capturamos la cuenta EXACTA y el saldo del pago
        counter_account = pay_arap_line.account_id.id
        
        # -------------------------------------------------------------------------
        # 2. Desvincular Y FORZAR ESTADO ABIERTO (Fix Definitivo)
        # -------------------------------------------------------------------------
        try:
            # Primero eliminamos los records de conciliación parcial
            payments.move_id.line_ids.mapped('matched_debit_ids').unlink()
            payments.move_id.line_ids.mapped('matched_credit_ids').unlink()
            _logger.info("[PAY-DBG] Se han eliminado conciliaciones parciales del pago.")

            # FIX CRÍTICO: Recalcular residual y forzar estado abierto.
            # Esto corrige el error "Está tratando de conciliar algunos asientos que ya han sido conciliados."
            payments.move_id.line_ids._compute_amount_residual()
            
            # REFRESCAR: Asegurar que tenemos la versión más reciente de la línea
            pay_arap_line = self.env['account.move.line'].browse(pay_arap_line.id)
            if pay_arap_line.reconciled:
                pay_arap_line.write({'reconciled': False}) 
            
            _logger.info("[PAY-DBG] Forzado re-cálculo de residuales y estado 'abierto'.")
            
        except Exception as e:
            _logger.warning("[PAY-DBG] No se pudo desvincular el pago (quizás ya estaba libre): %s", e)

        # -------------------------------------------------------------------------
        # 💰 CÁLCULO Y CREACIÓN DEL DIFERENCIAL (FX)
        # -------------------------------------------------------------------------
        fx_bs = self.company_currency_id.round(float(self.amount_diff or 0.0))
        company_cur = self.company_currency_id
        move_fx = self.env['account.move']

        if not company_cur.is_zero(fx_bs):
            # Lógica de Signos AUTOMÁTICA (Bulletproof)
            # Queremos que la diferencia RESTE disponibilidad al pago.
            monto_fx = abs(fx_bs)
            
            if pay_arap_line.debit > 0:
                # Pago es Débito (e.g., Pago a proveedor) -> FX debe ser Crédito
                partner_debit, partner_credit = 0.0, monto_fx
            else:
                # Pago es Crédito (e.g., Pago de cliente) -> FX debe ser Débito
                partner_debit, partner_credit = monto_fx, 0.0

            # Definir cuentas de Gasto/Ingreso según el signo de fx_bs
            income_acc = self.company_id.income_currency_exchange_account_id.id
            expense_acc = self.company_id.expense_currency_exchange_account_id.id
            account_dif_fx = expense_acc if fx_bs > 0 else income_acc

            # La contrapartida de la cuenta de Gasto/Ingreso
            dif_debit = partner_credit
            dif_credit = partner_debit
            
            # --- Helper para crear líneas ---
            def _mk_line_fx(account_id, debit, credit, label):
                return (0, 0, {
                    'partner_id': self.partner_id.id,
                    'account_id': account_id,
                    'name': label,
                    'debit': debit,
                    'credit': credit,
                    'currency_id': company_cur.id,
                })

            label_fx = (self.communication or '') + " (Dif. Cambiaria)"
            
            # Crear asiento FX
            partner_line_vals = _mk_line_fx(counter_account, partner_debit, partner_credit, label_fx)
            dif_line_vals = _mk_line_fx(account_dif_fx, dif_debit, dif_credit, label_fx)

            move_fx = self.env['account.move'].create({
                'ref': label_fx,
                'date': self.payment_date,
                'journal_id': self.journal_id_dif.id or self.journal_id.id,
                'line_ids': [dif_line_vals, partner_line_vals],
                'move_type': 'entry',
            })
            move_fx.action_post()
            payments.move_id_dif = move_fx # Guardamos referencia

            # ---------------------------------------------------------------------
            # 🔗 CONCILIACIÓN 1: PAGO (Parcial) <-> DIFERENCIA
            # ---------------------------------------------------------------------
            try:
                fx_line_to_rec = move_fx.line_ids.filtered(
                    lambda l: l.account_id.id == counter_account and l.partner_id == self.partner_id
                )
                
                # REFRESCAR: Asegurar que tenemos la versión más reciente de las líneas
                pay_arap_line = self.env['account.move.line'].browse(pay_arap_line.id)
                if fx_line_to_rec:
                    fx_line_to_rec = self.env['account.move.line'].browse(fx_line_to_rec.ids)

                if not fx_line_to_rec:
                    _logger.warning("[PAY-DBG] ⚠️ No se encontró línea de diferencial para conciliar.")
                else:
                    # 1. Verificar y corregir PAY_ARAP_LINE
                    if pay_arap_line.reconciled:
                        _logger.warning("[PAY-DBG] ⚠️ La línea de pago %s sigue marcada como conciliada. Intentando liberar.", pay_arap_line.id)
                        # Si está conciliada, verificamos si podemos liberarla
                        pay_arap_line.mapped('matched_debit_ids').unlink()
                        pay_arap_line.mapped('matched_credit_ids').unlink()
                        pay_arap_line._compute_amount_residual()
                        
                        # Forzar escritura si sigue True
                        if pay_arap_line.reconciled:
                             _logger.info("[PAY-DBG] 🔨 Forzando reconciled=False en Pago %s.", pay_arap_line.id)
                             pay_arap_line.write({'reconciled': False})

                    # 2. Verificar y corregir FX_LINE_TO_REC
                    if fx_line_to_rec.reconciled:
                        _logger.info("[PAY-DBG] 🔨 Forzando reconciled=False en FX %s.", fx_line_to_rec.id)
                        fx_line_to_rec.write({'reconciled': False})

                    # 3. Conciliar
                    _logger.info("[PAY-DBG] Intentando conciliar Pago %s (Res: %.2f) con FX %s (Res: %.2f)", 
                                 pay_arap_line.id, pay_arap_line.amount_residual, 
                                 fx_line_to_rec.id, fx_line_to_rec.amount_residual)
                    
                    (pay_arap_line + fx_line_to_rec).reconcile()
                    _logger.info("[PAY-DBG] ✅ Conciliado Pago con Diferencial. Saldo ajustado a: %.2f", pay_arap_line.amount_residual)

            except Exception as e:
                _logger.error("[PAY-DBG] Falló conciliación Pago-FX (Error final, revisar data): %s", e)

        # -------------------------------------------------------------------------
        # 🔗 CONCILIACIÓN 2: PAGO (Restante) <-> FACTURAS ORIGINALES
        # -------------------------------------------------------------------------
        invoices = self.line_ids.mapped('move_id').filtered(
            lambda m: m.is_invoice(include_receipts=True) and m.state == 'posted'
        )
        
        # SE OMITE POR REQUERIMIENTO: El usuario desea conciliar manualmente el pago con la factura.
        _logger.info("[PAY-DBG] ⏭️ Saltando conciliación automática con factura (Modo Manual).")

        # 3. Recomputes (Aseguramos que todos los saldos se actualicen)
        moves_to_recompute = self.env['account.move']
        moves_to_recompute |= payments.move_id
        if move_fx: 
            moves_to_recompute |= move_fx
        if invoices: 
            moves_to_recompute |= invoices
        
        for mv in moves_to_recompute:
            try:
                mv.line_ids._compute_amount_residual()
                mv._compute_amount()
            except:
                pass

        _logger.info("[PAY-DBG] === FIN _create_payments ===")
        return payments

    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        ###print(fields_list)
        #if 'line_ids' in fields_list:
        #    fields_list.remove("line_ids")
        if 'line_ids' in fields_list:
            fields_list.remove("line_ids")
        res = super().default_get(fields_list)
        fields_list.append("line_ids")
        if 'line_ids' in fields_list and 'line_ids' not in res:

            # Retrieve moves to pay from the context.

            if self._context.get('active_model') == 'account.move':
                lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
            elif self._context.get('active_model') == 'account.move.line':
                lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
            else:
                raise UserError(_(
                    "The register payment wizard should only be called on account.move or account.move.line records."
                ))

            # Keep lines having a residual amount to pay.
            available_lines = self.env['account.move.line']
            for line in lines:
                if line.move_id.state != 'posted':
                    raise UserError(_("You can only register payment for posted journal entries."))

                if line.account_type not in ('asset_receivable', 'liability_payable'):
                    continue
                if line.currency_id:
                    if line.move_id.amount_residual_usd == 0.0:
                        continue
                else:
                    if line.company_currency_id.is_zero(line.amount_residual) and line.move_id.amount_residual_usd == 0.0:
                        continue
                available_lines |= line

            # Check.
            if len(lines.company_id) > 1:
                raise UserError(_("You can't create payments for entries belonging to different companies."))
            if len(set(available_lines.mapped('account_type'))) > 1:
                raise UserError(
                    _("You can't register payments for journal items being either all inbound, either all outbound."))

            res['line_ids'] = [(6, 0, available_lines.ids)]
        
        # Parche: Set tax_invoice (tasa de la factura) correctamente al abrir el wizard
        if 'line_ids' in res and res['line_ids']:
            # Puede ser lista de comandos tipo [(6, 0, [ids...])] o lista de ints (ids)
            if isinstance(res['line_ids'][0], tuple) and res['line_ids'][0][0] == 6:
                # Comando Odoo: [(6, 0, [ids...])]
                lines_ids = res['line_ids'][0][2]
            else:
                # Ya es lista de IDs directamente
                lines_ids = res['line_ids']
            lines = self.env['account.move.line'].browse(lines_ids)
            factura = lines.mapped('move_id')
            if factura and hasattr(factura[0], 'tax_today'):
                res['tax_invoice'] = factura[0].tax_today or 1.0

        return res