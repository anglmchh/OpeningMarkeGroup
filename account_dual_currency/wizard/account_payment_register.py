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
        """
        Crea el pago.
        1. Fuerza 'payment_difference_handling' a 'open' siempre.
        2. Bloquea la conciliación automática Pago ↔ Factura del super().
        3. Si hay diferencial FX, crea el asiento FX y concilia Pago ↔ Asiento FX.
        """
        _logger.info("[PAY-DBG] === INICIO _create_payments (CONCILIACIÓN SOLO PAGO-FX) ===")

        company_cur = self.company_currency_id
        fx_bs = company_cur.round(float(self.amount_diff or 0.0))
        has_fx_diff = not company_cur.is_zero(fx_bs)

        # CRÍTICO: 1. Forzar el manejo de diferencia a 'open' SIEMPRE.
        ctx = self.env.context.copy()
        ctx['payment_difference_handling'] = 'open'
        ctx['writeoff_account_id'] = False
        ctx['writeoff_label'] = False
        
        # CRÍTICO: 2. Bloquear la conciliación automática Pago ↔ Factura en el super().
        payments = super(AccountPaymentRegister, self.with_context(
            ctx, 
            tasa_factura=self.tax_today,
            calcular_dual_currency=True,
            lines_to_reconcile=self.env['account.move.line'],
        ))._create_payments()

        if not payments or not payments.move_id:
            _logger.error("[PAY-DBG] No se obtuvo payments.move_id desde super(). Abortando.")
            return payments

        invoices = self.line_ids.mapped('move_id').filtered(
            lambda m: m.state == 'posted' and m.is_invoice(include_receipts=True)
        )

        # === 2.1. CRÍTICO: ANULAR CONCILIACIÓN AUTOMÁTICA PAGO ↔ FACTURA ===
        pay_lines = payments.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        inv_moves = invoices.ids

        partials_to_unlink = self.env['account.partial.reconcile']
        
        for pl in pay_lines:
            partials = pl.matched_debit_ids | pl.matched_credit_ids
            for p in partials:
                target_move_line = p.debit_move_id if p.debit_move_id.id != pl.id else p.credit_move_id
                target_move = target_move_line.move_id
                
                if target_move.id in inv_moves:
                    partials_to_unlink |= p
                    
        if partials_to_unlink:
            _logger.info("[PAY-DBG] Eliminando %s registros de conciliación parcial automática (Pago ↔ Factura) para forzar la apertura.", len(partials_to_unlink))
            partials_to_unlink.unlink()
            
            # FIX DE CACHÉ: Invalidación general sobre los modelos afectados.
            # Usamos invalidate_recordset en los recordsets de líneas
            pay_lines.invalidate_recordset(['amount_residual', 'amount_residual_currency'])
            invoices.mapped('line_ids').invalidate_recordset(['amount_residual', 'amount_residual_currency'])
            
            moves_to_recompute_unlink = payments.move_id | invoices
            for mv in moves_to_recompute_unlink:
                try:
                    if hasattr(mv, 'invalidate_cache'): mv.invalidate_cache()
                    mv._compute_amount()
                except Exception as e:
                    _logger.debug("[PAY-DBG] Error de recompute/cache después de unlink: %s", e)
        # =======================================================================

        # === 3. PREPARACIÓN DE LÍNEAS AR/AP PARA LA CADENA ===
        # Re-fetch la línea base del pago para asegurar el saldo correcto después del unlink
        pay_arap_line_base = self.env['account.move.line'].browse(pay_lines.ids).filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            and l.partner_id == self.partner_id
            and not l.reconciled
        )[:1]
        
        move_fx = self.env['account.move']
        
        # Guardamos el balance de inicio para el cálculo esperado 
        pay_line_start_balance = 0.0
        if pay_arap_line_base:
            # FIX DE CACHÉ: Invalidación antes de leer el balance START
            pay_arap_line_base.invalidate_recordset(['balance', 'amount_residual']) 
            pay_line_start_balance = abs(pay_arap_line_base.balance)
            _logger.info("[PAY-DBG] [BALANCE START] Pago AR/AP Line ID %s. Balance INICIO (Total Pago): %.4f", pay_arap_line_base.id, pay_line_start_balance)
        
        
        # MODIFICACIÓN CRÍTICA: Se omite la validación de journal_id_dif del IF
        if has_fx_diff and pay_arap_line_base:
            
            # ASIGNACIÓN DEL DIARIO FX: Usa el diario diferencial si existe, si no, usa el diario de pago.
            journal_dif = self.journal_id_dif or self.journal_id
            
            _logger.info("[PAY-DBG] FX CHECK: FX_BS=%.4f | has_fx_diff=True | pay_line_found=True -> INICIANDO FX LOGIC.", fx_bs)
            
            company = self.company_id
            ref_cur = self.currency_id_dif or company.currency_id_dif
            inv_first = invoices[:1]
            mt = inv_first.move_type if inv_first else False
            is_vendor = bool(mt in ('in_invoice', 'in_refund', 'in_receipt')) or (self.payment_type == 'outbound')
            abs_fx = abs(fx_bs)
            counter_account = pay_arap_line_base.account_id.id
            
            # Lógica de Asiento FX para determinar débito/crédito
            income_acc = company.income_currency_exchange_account_id.id
            expense_acc = company.expense_currency_exchange_account_id.id

            if is_vendor:
                account_dif_fx = expense_acc if fx_bs > 0 else income_acc
            else:
                account_dif_fx = income_acc if fx_bs > 0 else expense_acc

            if is_vendor:
                partner_debit = abs_fx if fx_bs < 0 else 0.0
                partner_credit = abs_fx if fx_bs > 0 else 0.0
            else:
                partner_debit = abs_fx if fx_bs > 0 else 0.0
                partner_credit = abs_fx if fx_bs < 0 else 0.0
                
            dif_debit = partner_credit
            dif_credit = partner_debit

            # <LÓGICA DE CREACIÓN DEL move_fx>
            label_fx = (self.writeoff_label + ' - Dif Camb ' + (self.communication or '')).strip()

            def _mk_line_fx(account_id, debit=0.0, credit=0.0, label=label_fx):
                vals = {
                    'partner_id': self.partner_id.id if account_id == counter_account else False,
                    'date': self.payment_date,
                    'account_id': account_id,
                    'name': label,
                    'debit': debit,
                    'credit': credit,
                }
                return (0, 0, vals)

            partner_line_fx = _mk_line_fx(counter_account, debit=partner_debit, credit=partner_credit)
            dif_line_fx = _mk_line_fx(account_dif_fx, debit=dif_debit, credit=dif_credit)

            # CRÍTICO: NO pasamos currency_id_dif para que NO calcule valores duales.
            move_vals_fx = {
                'ref': label_fx,
                'line_ids': [dif_line_fx, partner_line_fx],
                'journal_id': journal_dif.id,
                'date': self.payment_date,
                'state': 'draft',
                'move_type': 'entry',
            }
            move_fx = self.env['account.move'].create(move_vals_fx)
            move_fx._post(soft=False)
            payments.move_id_dif = move_fx
            # </FIN LÓGICA DE CREACIÓN DEL move_fx>

            fx_partner_line = move_fx.line_ids.filtered(
                lambda l: l.account_id.id == counter_account and l.partner_id == self.partner_id
            )

            # CRÍTICO: Conciliación Pago ↔ Asiento FX por el monto del diferencial (abs_fx)
            if pay_arap_line_base.balance < 0:
                debit_line, credit_line = fx_partner_line, pay_arap_line_base
            else:
                debit_line, credit_line = pay_arap_line_base, fx_partner_line

            if abs_fx > 0 and debit_line and credit_line and debit_line.account_id == credit_line.account_id:
                try:
                    self.env['account.partial.reconcile'].create({
                        'debit_move_id': debit_line.id,
                        'credit_move_id': credit_line.id,
                        'amount': abs_fx, 
                        # FIX CRÍTICO: Aseguramos que la conciliación no use moneda extranjera (USD)
                        'debit_amount_currency': 0.0,
                        'credit_amount_currency': 0.0,
                    })
                    _logger.info(
                        "[PAY-DBG] CONCILIACIÓN PARCIAL EXITOSA: Pago %s y Asiento FX %s conciliados por %.4f Bs (DIFERENCIAL).",
                        payments.id, move_fx.id, abs_fx
                    )
                except Exception as e:
                    _logger.exception("[PAY-DBG] Error creando account.partial.reconcile (Pago ↔ FX): %s", e)
        else:
            _logger.info("[PAY-DBG] SALIDA del bloque FX. Diferencial (%.4f) o Línea de Pago no válida.", fx_bs)


        # === 4. NO SE REALIZA CONCILIACIÓN FINAL CON FACTURA ===
        _logger.info("[PAY-DBG] Omitting final reconcile with Invoice(s) per user request.")
        
        # === 5. Recomputes final de seguridad ===
        moves_to_recompute = payments.move_id | move_fx | invoices
        
        # Forzamos un recompute completo después de la conciliación
        for mv in moves_to_recompute:
            try:
                # FIX CRÍTICO: Usamos el método correcto en el recordset para invalidar el caché.
                mv.line_ids.invalidate_recordset(['amount_residual', 'amount_residual_currency'])
                
                if hasattr(mv, 'invalidate_cache'): mv.invalidate_cache()
                mv._compute_amount()
            except Exception as e:
                _logger.debug("[PAY-DBG] Ignorado error en recompute final: %s", e)
        
        # FIX CRÍTICO: Invalida el cache globalmente (último recurso)
        self.env.invalidate_all() 
        
        # --- DEBUG: CHECK ENDING BALANCE ---
        if payments.move_id:
            try:
                # Re-fetch the line to ensure we are reading fresh data
                pay_line_final = self.env['account.move.line'].browse(pay_arap_line_base.id)
                
                # Forzar un último read para asegurar que el ORM tiene el valor correcto.
                pay_line_final.refresh_all_models()
                residual = abs(pay_line_final.amount_residual)
                expected_residual = pay_line_start_balance - fx_bs if 'pay_line_start_balance' in locals() else 0.0
                
                _logger.info("[PAY-DBG] [BALANCE END] Pago Line ID %s. RESIDUAL ACTUAL (amount_residual): %.4f (Esperado: %.4f)", pay_line_final.id, residual, expected_residual)
            except Exception as e:
                _logger.debug("[PAY-DBG] Error al calcular balance final: %s", e)
        # -----------------------------------

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