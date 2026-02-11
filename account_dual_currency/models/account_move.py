# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)
import json
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
        
    currency_id_dif = fields.Many2one("res.currency",
                                     string="Moneda Dual Ref.",
                                     default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )

    acuerdo_moneda = fields.Boolean(string="Acuerdo de Factura Bs.", default=False)

    tax_today = fields.Float(string="Tasa", store=True,
                              default=lambda self: self.env.company.currency_id_dif.inverse_rate,
                              tracking=True, digits='Dual_Currency_rate')

    tax_today_edited = fields.Boolean(string="Tasa editada", default=False)

    edit_trm = fields.Boolean(string="Editar tasa", compute='_edit_trm')

    name_rate = fields.Char(string='Tasa de Referencia Temp')
    amount_untaxed_usd = fields.Monetary(currency_field='currency_id_dif', string="Base imponible Ref.", store=True,
                                         compute="_amount_all_usd", digits='Dual_Currency', copy=False)
    amount_tax_usd = fields.Monetary(currency_field='currency_id_dif', string="Impuestos Ref.", store=True,
                                     readonly=True, digits='Dual_Currency', compute="_amount_all_usd", copy=False)
    amount_total_usd = fields.Monetary(currency_field='currency_id_dif', string='Total Ref.', store=True, readonly=True,
                                       compute='_amount_all_usd',
                                       digits='Dual_Currency', tracking=True)

    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif', compute='_compute_amount', string='Adeudado Ref.',
                                          readonly=True, digits='Dual_Currency', store=True, copy=False)
    invoice_payments_widget_usd = fields.Binary(groups="account.group_account_invoice,account.group_account_readonly",
                                              compute='_compute_payments_widget_reconciled_info_USD')

    amount_untaxed_bs = fields.Monetary(currency_field='company_currency_id', string="Base imponible Bs.", store=True, copy=False,
                                         compute="_amount_all_usd")
    amount_tax_bs = fields.Monetary(currency_field='company_currency_id', string="Impuestos Bs.", compute="_amount_all_usd", store=True, copy=False,
                                    readonly=True)
    amount_total_bs = fields.Monetary(currency_field='company_currency_id', string='Total Bs.', store=True,
                                      readonly=True,
                                      compute='_amount_all_usd', copy=False)

    amount_total_signed_usd = fields.Monetary(
        string='Total Ref.',
        compute='_compute_amount', store=True, readonly=True,
        currency_field='currency_id_dif', copy=False
    )

    invoice_payments_widget_bs = fields.Text(groups="account.group_account_invoice", copy=False)

    same_currency = fields.Boolean(string="Mismo tipo de moneda", compute='_same_currency')

    verificar_pagos = fields.Boolean(string="Verificar pagos", compute='_verificar_pagos')

    asset_remaining_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Valor depreciable Ref.', copy=False, compute='_compute_depreciation_cumulative_value_ref')
    asset_depreciated_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Depreciación Acu. Ref.', copy=False, compute='_compute_depreciation_cumulative_value_ref')

    # --- ✨ CAMPOS IGTF CORREGIDOS Y MEJORADOS ---
    aplicar_igtf = fields.Boolean(string="Aplica IGTF")
    journal_igtf_id = fields.Many2one(
        'account.journal',
        string='Diario IGTF',
        check_company=True
    )
    mount_igtf = fields.Monetary(
        currency_field='company_currency_id', # <-- ESTE ES EL CAMPO CORRECTO
        string='Monto IGTF',
        readonly=True
    )
    move_igtf_id = fields.Many2one(
        'account.move',
        'Asiento IGTF',
        readonly=True,
        copy=False
    )

    depreciation_value_ref = fields.Monetary(
        string="Depreciation Ref.",
        compute="_compute_depreciation_value_ref", inverse="_inverse_depreciation_value_ref", store=True, copy=False
    )

    def _post(self, soft=True):
        
        # Inyectamos el contexto de bloqueo antes de nada.
        # Esto soluciona el problema de IVA que cambia al publicar.
        moves_to_post = self.with_context(skip_tax_today_onchange=True)

        for move in moves_to_post:
            # =================================================================
            # LOGS PRE-POST: Verificamos los valores ANTES de la publicación
            # =================================================================
            _logger.info("===================================================================")
            _logger.info(f"[DUAL POST] INICIO Post de Factura ID: {move.id} - Nombre: {move.name}")
            _logger.info(f"[DUAL POST] Tasa actual (tax_today): {move.tax_today}")
            
            move._compute_tax_totals()
            tax_totals_info = move.tax_totals or {}
            
            untaxed_amount_pre = tax_totals_info.get('amount_untaxed', 0.0)
            tax_amount_pre = tax_totals_info.get('amount_tax', 0.0)
            total_amount_pre = tax_totals_info.get('amount_total', 0.0)
            
            _logger.info(f"[DUAL POST] PRE-POST - Base Imponible: {untaxed_amount_pre}")
            _logger.info(f"[DUAL POST] PRE-POST - Monto Impuesto (IVA): {tax_amount_pre}")
            _logger.info(f"[DUAL POST] PRE-POST - Monto Total: {total_amount_pre}")
            _logger.info("===================================================================")

        
        res = super(AccountMove, moves_to_post)._post(soft=soft)
        
        for move in res:
            # =================================================================
            # LOGS POST-POST: Verificamos los valores DESPUÉS de la publicación
            # =================================================================
            move._compute_tax_totals()
            tax_totals_info_post = move.tax_totals or {}
            
            untaxed_amount_post = tax_totals_info_post.get('amount_untaxed', 0.0)
            tax_amount_post = tax_totals_info_post.get('amount_tax', 0.0)
            total_amount_post = tax_totals_info_post.get('amount_total', 0.0)
            
            _logger.info("===================================================================")
            _logger.info(f"[DUAL POST] FINAL Post de Factura ID: {move.id} - Nombre: {move.name}")
            _logger.info(f"[DUAL POST] Tasa final (tax_today): {move.tax_today}")
            
            _logger.info(f"[DUAL POST] POST-POST - Base Imponible: {untaxed_amount_post} (Diferencia: {untaxed_amount_post - untaxed_amount_pre:.6f})")
            _logger.info(f"[DUAL POST] POST-POST - Monto Impuesto (IVA): {tax_amount_post} (Diferencia: {tax_amount_post - tax_amount_pre:.6f})")
            _logger.info(f"[DUAL POST] POST-POST - Monto Total: {total_amount_post} (Diferencia: {total_amount_post - total_amount_pre:.6f})")
            _logger.info("===================================================================")
            
            move._verificar_pagos() 
            
        return res

    @api.depends('asset_id', 'depreciation_value', 'asset_id.total_depreciable_value', 'asset_id.already_depreciated_amount_import')
    def _compute_depreciation_cumulative_value(self):
        super(AccountMove, self)._compute_depreciation_cumulative_value()
        for move in self:
            if move.asset_id:
                move.asset_remaining_value_ref = (move.asset_remaining_value / move.tax_today) if move.tax_today != 0 else 0
                move.asset_depreciated_value_ref = (move.asset_depreciated_value / move.tax_today) if move.tax_today != 0 else 0

    @api.depends('line_ids.balance_usd')
    def _compute_depreciation_value_ref(self):
        for move in self:
            asset = move.asset_id or move.reversed_entry_id.asset_id 
            if asset:
                account = asset.account_depreciation_expense_id if asset.asset_type != 'sale' else asset.account_depreciation_id
                asset_depreciation = sum(
                    move.line_ids.filtered(lambda l: l.account_id == account).mapped('balance_usd')
                )
                if any(
                        line.account_id == asset.account_asset_id
                        and float_compare(-line.balance_usd, asset.original_value_ref,
                                             precision_rounding=asset.currency_id.rounding) == 0
                        for line in move.line_ids
                ):
                    account = asset.account_depreciation_id
                    asset_depreciation = (
                                asset.original_value_ref
                                - asset.salvage_value_ref
                                - sum(
                            move.line_ids.filtered(lambda l: l.account_id == account).mapped(
                                'debit_usd' if asset.original_value_ref > 0 else 'credit_usd'
                            )
                        ) * (-1 if asset.original_value_ref < 0 else 1)
                    )
            else:
                asset_depreciation = 0
            move.depreciation_value_ref = asset_depreciation

    def _inverse_depreciation_value(self):
        for move in self:
            asset = move.asset_id
            amount = abs(move.depreciation_value_ref)
            account = asset.account_depreciation_expense_id if asset.asset_type != 'sale' else asset.account_depreciation_id
            move.write({'line_ids': [
                Command.update(line.id, {
                    'balance_usd': amount if line.account_id == account else -amount,
                })
                for line in move.line_ids
            ]})

    def _verificar_pagos(self):
        for rec in self:
            for line in rec.line_ids:
                if line.balance_usd == 0:
                    line._compute_balance_usd()
                line._compute_amount_residual_usd()
            rec.verificar_pagos = True

    @api.depends('invoice_date', 'company_id')
    def _compute_date(self):
        res = super(AccountMove, self)._compute_date()
        for rec in self:
            if rec.invoice_date and rec.company_id.currency_id_dif and not rec.tax_today_edited:
                new_rate_ids = self.env.company.currency_id_dif._get_rates(self.env.company, rec.invoice_date)
                if new_rate_ids:
                    new_rate = 1 / new_rate_ids[self.env.company.currency_id_dif.id]
                    rec.tax_today = new_rate

    def _fecha_para_tax_today(self, vals=None):
        if (vals and vals.get('move_type') == 'entry') or (not vals and self.move_type == 'entry'):
            if vals:
                return vals.get('date') or self.date
            return self.date
        if vals:
            return vals.get('invoice_date') or vals.get('date') or self.invoice_date or self.date
        return self.invoice_date or self.date
    
    def _get_tasa_usd_by_date(self, fecha, company=None):
        if isinstance(fecha, (fields.Date.__class__,)):
            fecha_str = fields.Date.to_string(fecha)
        else:
            fecha_str = str(fecha)
        usd = self.env.ref('base.USD')
        company = company or self.env.company
        tasa = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd.id),
            ('name', '=', fecha_str),
            ('company_id', '=', company.id)
        ], limit=1)
        return tasa.inverse_company_rate if tasa else 1.0

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move, vals in zip(moves, vals_list):
            j = move.journal_id
            is_fx_journal = bool(getattr(j, 'is_exchange_diff_journal', False) or
                                getattr(j, 'is_fx_diff_journal', False))

            if is_fx_journal and move.move_type == 'entry':
                # Asientos de DIF CAMBIO
                if move.tax_today != 0.0:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': 0.0})
                move.line_ids.write({
                    'tax_today': 0.0,
                    'debit_usd': 0.0,
                    'credit_usd': 0.0,
                    'balance_usd': 0.0,
                })
                _logger.info("[DUAL] create(): move %s (FX diff) -> tasa=0 y dual=0", move.id)

            else:
                # Documentos normales (facturas/pagos)
                if move.move_type in ('out_refund', 'in_refund'):
                    continue 

                if vals.get('tax_today'):
                    continue 

                fecha = move._fecha_para_tax_today()
                tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
                if move.tax_today != tasa:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': tasa})

                # Asegurar recompute dual currency en líneas
                try:
                    lines = move.line_ids
                    # CORRECCIÓN DE ERROR (AttributeError): Llamamos al método por su nombre
                    lines._debit_usd()        
                    lines._credit_usd()       
                    lines._compute_balance_usd()
                    _logger.info("[DUAL] create(): move %s recompute dual OK", move.id)
                except Exception as e:
                    _logger.exception("[DUAL] create(): fallo recompute dual en move %s: %s", move.id, e)

        return moves


    def write(self, vals):
        if self.env.context.get('skip_tax_today_update'):
            return super().write(vals)

        res = super().write(vals)

        for move in self:
            j = move.journal_id
            is_fx_journal = bool(getattr(j, 'is_exchange_diff_journal', False) or
                                getattr(j, 'is_fx_diff_journal', False))

            if is_fx_journal and move.move_type == 'entry':
                # Mantener tasa=0 y dual=0 en asientos de DIF CAMBIO
                if move.tax_today != 0.0:
                    super(AccountMove, move.with_context(skip_tax_today_update=True)).write({'tax_today': 0.0})
                move.line_ids.write({
                    'tax_today': 0.0,
                    'debit_usd': 0.0,
                    'credit_usd': 0.0,
                    'balance_usd': 0.0,
                })
                _logger.info("[DUAL] write(): move %s (FX diff) -> tasa=0 y dual=0", move.id)

            else:
                # Documentos normales (facturas/pagos)
                necesita_recalc = any(k in vals for k in ('date', 'invoice_date', 'move_type', 'company_id'))

                if not necesita_recalc:
                    continue

                if move.move_type in ('out_refund', 'in_refund'):
                    continue 

                if 'tax_today' in vals:
                    continue 

                fecha = move._fecha_para_tax_today(vals)
                tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
                if move.tax_today != tasa:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': tasa})

                # Asegurar recompute dual currency en líneas
                try:
                    lines = move.line_ids
                    # CORRECCIÓN DE ERROR (AttributeError): Llamamos al método por su nombre
                    lines._debit_usd()        
                    lines._credit_usd()       
                    lines._compute_balance_usd()
                    _logger.info("[DUAL] write(): move %s recompute dual OK", move.id)
                except Exception as e:
                    _logger.exception("[DUAL] write(): fallo recompute dual en move %s: %s", move.id, e)

        return res

    @api.depends('currency_id')
    def _same_currency(self):
        self.same_currency = self.currency_id == self.env.company.currency_id


    @api.onchange('tax_today')
    def _onchange_tax_today(self):
        """
        Bloquea la lógica de recalculo de factura si viene de SO (evita error 13.5k) 
        o está en proceso de publicación (evita cambio de IVA al postear).
        """
        # BLOQUEO CRÍTICO: Si el flag está presente (creación desde SO en Bs o posteo), OMITIMOS la lógica de precios.
        if self.env.context.get('skip_dual_currency_conversion') or self.env.context.get('skip_tax_today_onchange'):
            return 
        
        self = self.with_context(check_move_validity=False)
        for rec in self:
            rec.tax_today_edited = True
            
            if not rec.move_type == 'entry':
                # La lógica original que causó el error de Attribute y el IVA absurdo (al recalcular price_unit)
                # se elimina para facturas/recibos, obligando a Odoo a usar los valores estables.
                
                # El for de lineas y la línea que usaba price_unit_usd se eliminan aquí.

                rec._onchange_quick_edit_total_amount()
                rec._onchange_quick_edit_line_ids()
                rec._compute_tax_totals() 

                rec.invoice_line_ids._compute_totals()
            else:
                # Lógica para asientos de diario (entry), donde SÍ se recalcula débito/crédito.
                for aml in rec.line_ids:
                    if aml.debit_usd > 0:
                        aml.with_context(check_move_validity=False).debit = aml.debit_usd * rec.tax_today
                    elif aml.debit_usd == 0 and aml.debit > 0:
                        aml.with_context(check_move_validity=False).debit_usd = (aml.debit / rec.tax_today) if rec.tax_today > 0 else 0
                    if aml.credit_usd > 0:
                        aml.with_context(check_move_validity=False).credit = aml.credit_usd * rec.tax_today
                    elif aml.credit_usd == 0 and aml.credit > 0:
                        aml.with_context(check_move_validity=False).credit_usd = (aml.credit / rec.tax_today) if rec.tax_today > 0 else 0

    @api.onchange('currency_id')
    def _onchange_currency(self):
        for rec in self:
            # 💥 CORRECCIÓN: Se eliminan referencias a l.price_unit_usd en _onchange_currency
            if rec.currency_id == self.env.company.currency_id:
                for l in rec.invoice_line_ids:
                    l.currency_id = rec.currency_id
                    # Lógica ajustada: asumiendo que el precio no debe cambiar si la moneda pasa a ser local
                    # y no tenemos price_unit_usd para recalcular.
                    l.price_unit = l.price_unit 
            else:
                for l in rec.invoice_line_ids:
                    l.currency_id = rec.currency_id
                    l.price_unit = l.price_unit # Mantener el precio actual
            
            for aml in rec.line_ids:
                aml.currency_id = rec.currency_id
                aml._compute_currency_rate()

    @api.depends('state', 'move_type')
    def _edit_trm(self):
        for rec in self:
            edit_trm = False
            if rec.move_type in ('in_invoice', 'in_refund', 'in_receipt', 'entry'):
                if rec.state == 'draft' and not rec.acuerdo_moneda:
                    edit_trm = True
                else:
                    edit_trm = False
            else:
                edit_trm = self.env.user.has_group('account_dual_currency.group_edit_trm')
                if edit_trm:
                    if rec.state == 'draft' and not rec.acuerdo_moneda:
                        edit_trm = True
                    else:
                        edit_trm = False
            # ##print(edit_trm)
            rec.edit_trm = edit_trm

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id','tax_today', 'state')
    def _compute_amount(self):
        for move in self:
            self.env.context = dict(self.env.context, tasa_factura=move.tax_today, calcular_dual_currency=True)
            super(AccountMove, self)._compute_amount()
            total_residual = 0.0
            total = 0.0
            for line in move.line_ids:
                if move.is_invoice(True):
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total += line.balance_usd
                    elif line.display_type in ('product', 'rounding'):
                        total += line.balance_usd
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual_usd
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
            move.amount_residual_usd = total_residual
            move.amount_total_signed_usd = abs(total) if move.move_type == 'entry' else -total
        self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)
    @api.depends(
        'tax_totals',
        'currency_id_dif',
        'currency_id','tax_today')
    def _amount_all_usd(self):
        for rec in self:
            if rec.is_invoice(include_receipts=True) and rec.tax_totals:
                amount_untaxed = rec.tax_totals['amount_untaxed'] if rec.tax_totals['amount_untaxed'] else 0
                amount_tax = 0
                for product, income in rec.tax_totals['groups_by_subtotal'].items():
                    # print(product, income)
                    for l in income:
                        amount_tax += l['tax_group_amount']
                        print(l['tax_group_amount'])
                        
                print(f'amount tax: {amount_tax}')
                amount_total = rec.tax_totals['amount_total']
                if rec.currency_id != self.env.company.currency_id:
                    rec.amount_untaxed_usd = rec.amount_untaxed
                    print(f'amount tax if: {amount_tax}')
                    rec.amount_tax_usd = rec.amount_tax
                    rec.amount_total_usd = rec.amount_total
                    print(f' tax  today if: {rec.tax_today}')
                    rec.amount_untaxed_bs = rec.amount_untaxed_usd * rec.tax_today
                    rec.amount_tax_bs = rec.amount_tax * rec.tax_today 
                    rec.amount_total_bs = rec.amount_total_usd * rec.tax_today
                else:
                    rec.amount_untaxed_usd = (amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0
                    rec.amount_tax_usd = (amount_tax / rec.tax_today) if rec.tax_today > 0 else 0
                    rec.amount_total_usd = (amount_total / rec.tax_today) if rec.tax_today > 0 else 0
                    rec.amount_untaxed_bs = rec.amount_untaxed 
                    print(f' tax  today else: {rec.tax_today}')
                    
                    rec.amount_tax_bs = rec.amount_tax
                    rec.amount_total_bs = rec.amount_total
            else:
                rec.amount_untaxed_usd = 0
                rec.amount_tax_usd = 0
                rec.amount_total_usd = 0
                rec.amount_untaxed_bs = 0
                rec.amount_tax_bs = 0
                rec.amount_total_bs = 0

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_USD(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            total_pagado = 0
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials_USD()

                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False
                    total_pagado = total_pagado + float(reconciled_partial['amount'])
                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'amount': reconciled_partial['amount'],
                        'currency_id': move.company_id.currency_id_dif.id if move.company_id.currency_id_dif else
                        move.company_id.currency_id.id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance_usd),
                                                              currency_obj=counterpart_line.company_id.currency_id_dif),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env,
                                                                                   abs(counterpart_line.amount_currency),
                                                                                   currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget_usd = payments_widget_vals
                if total_pagado < move.amount_total_usd:
                    move.amount_residual_usd = move.amount_total_usd - total_pagado
                else:
                    move.amount_residual_usd = 0
                # if move.amount_residual_usd > 0:
                #     move.payment_state = 'partial'
                # else:
                #     move.payment_state = 'paid'
            else:
                move.amount_residual_usd = move.amount_total_usd
                move.invoice_payments_widget_usd = False

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_bs(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_bs = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_bs()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                move.invoice_payments_widget_bs = json.dumps(info, default=date_utils.json_default)
            else:
                move.invoice_payments_widget_bs = json.dumps(False)

    def _get_reconciled_info_JSON_values_bs(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id

            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            if counterpart_line.credit > 0:
                amount = counterpart_line.credit
            else:
                amount = counterpart_line.debit

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': partial.amount,
                'currency': self.currency_id_dif.symbol,
                'digits': [69, 2],
                'position': self.currency_id_dif.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        # ##print(reconciled_vals)
        return reconciled_vals

    def _get_all_reconciled_invoice_partials_USD(self):
        self.ensure_one()
        reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        if not reconciled_lines:
            return {}

        query = '''
            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.credit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.debit_move_id IN %s

            UNION ALL

            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.debit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.credit_move_id IN %s
        '''
        self._cr.execute(query, [tuple(reconciled_lines.ids)] * 2)

        partial_values_list = []
        counterpart_line_ids = set()
        exchange_move_ids = set()
        for values in self._cr.dictfetchall():
            partial_values_list.append({
                'aml_id': values['counterpart_line_id'],
                'partial_id': values['id'],
                'amount': values['amount'],
                'currency': self.currency_id,
            })
            counterpart_line_ids.add(values['counterpart_line_id'])
            if values['exchange_move_id']:
                exchange_move_ids.add(values['exchange_move_id'])

        if exchange_move_ids:
            query = '''
                SELECT
                    part.id,
                    part.credit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
                WHERE credit_line.move_id IN %s AND part.debit_move_id IN %s

                UNION ALL

                SELECT
                    part.id,
                    part.debit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
                WHERE debit_line.move_id IN %s AND part.credit_move_id IN %s
            '''
            self._cr.execute(query, [tuple(exchange_move_ids), tuple(counterpart_line_ids)] * 2)

            for values in self._cr.dictfetchall():
                counterpart_line_ids.add(values['counterpart_line_id'])
                partial_values_list.append({
                    'aml_id': values['counterpart_line_id'],
                    'partial_id': values['id'],
                    'currency': self.company_id.currency_id,
                })

        counterpart_lines = {x.id: x for x in self.env['account.move.line'].browse(counterpart_line_ids)}
        for partial_values in partial_values_list:
            aml = counterpart_lines[partial_values['aml_id']]
            partial_values['aml'] = aml
            partial_values['is_exchange'] = aml.move_id.id in exchange_move_ids
            # Si es un movimiento de exchange, usamos el balance_usd del aml.
            if partial_values['is_exchange']:
                partial_values['amount'] = abs(aml.balance_usd)
            else:
                # Fallback: si en la tabla parcial no vino amount (o es 0), usamos aml.balance_usd
                # Esto evita que pagos en Bs no muestren su equivalente en USD en el widget.
                db_amount = partial_values.get('amount') or 0.0
                if not db_amount:
                    partial_values['amount'] = abs(getattr(aml, 'balance_usd', 0.0))
                else:
                    partial_values['amount'] = db_amount

        return partial_values_list

    # def js_assign_outstanding_line(self, line_id):
    #     lines = super(AccountMove, self).js_assign_outstanding_line(line_id)
    #     line_ids = self.env['account.move.line'].browse(line_id)
    #     line_ids._compute_amount_residual_usd()
    #     return lines

    # def js_assign_outstanding_line(self, line_id):
    #     ''' Called by the 'payment' widget to reconcile a suggested journal item to the present
    #     invoice.
    #
    #     :param line_id: The id of the line to reconcile with the current invoice.
    #     '''
    #     self.ensure_one()
    #     lines = self.env['account.move.line'].browse(line_id)
    #     l = self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
    #     if abs(lines[0].amount_residual) == 0 and abs(lines[0].amount_residual_usd) > 0:
    #         if l.full_reconcile_id:
    #             l.full_reconcile_id.unlink()
    #         partial = self.env['account.partial.reconcile'].create([{
    #             'amount': 0,
    #             'amount_usd': l.move_id.amount_residual_usd if abs(
    #                 lines[0].amount_residual_usd) > l.move_id.amount_residual_usd else abs(
    #                 lines[0].amount_residual_usd),
    #             'debit_amount_currency': 0,
    #             'credit_amount_currency': 0,
    #             'debit_move_id': l.id,
    #             'credit_move_id': line_id,
    #         }])
    #         p = (lines + l).reconcile()
    #         (lines + l)._compute_amount_residual_usd()
    #         return p
    #     else:
    #         results = (lines + l).reconcile()
    #         if 'partials' in results:
    #             if results['partials'].amount_usd == 0:
    #                 monto_usd = 0
    #                 if abs(lines[0].amount_residual_usd) > 0:
    #
    #                     # ##print("1")
    #                     if abs(lines[0].amount_residual_usd) > self.amount_residual_usd:
    #                         # ##print("2")
    #                         monto_usd = self.amount_residual_usd
    #                     else:
    #                         # ##print("3")
    #                         monto_usd = abs(lines[0].amount_residual_usd)
    #                 results['partials'].write({'amount_usd': monto_usd})
    #                 lines[0]._compute_amount_residual_usd()
    #         return results

    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|','|', ('amount_residual', '!=', 0.0), ('amount_residual_usd', '!=', 0.0),('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_usd) > 0:
                        payments_widget_vals['content'].append({
                            'journal_name': line.ref or line.move_id.name,
                            'amount': 0,
                            'amount_usd': abs(line.amount_residual_usd),
                            'currency_id': move.currency_id.id,
                            'currency_id_dif': move.currency_id_dif.id,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'date': fields.Date.to_string(line.date),
                            'account_payment_id': line.payment_id.id,
                        })
                        continue
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                    amount_usd = abs(line.amount_residual_usd)
                else:
                    # Different foreign currencies.
                    amount = line.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )
                    amount_usd = abs(line.amount_residual_usd)

                if move.currency_id.is_zero(amount) and amount_usd == 0:
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'amount_usd': amount_usd,
                    'currency_id': move.currency_id.id,
                    'currency_id_dif': move.currency_id_dif.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue
            ###print(payments_widget_vals)
            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        move_vals = super(AccountMove, self)._prepare_move_for_asset_depreciation(vals)
        asset_id = vals.get('asset_id')
        move_vals['tax_today'] = asset_id.tax_today
        move_vals['currency_id_dif'] = asset_id.currency_id_dif.id
        #move_vals['asset_remaining_value_ref'] = move_vals['asset_remaining_value'] / asset_id.tax_today
        #move_vals['asset_depreciated_value_ref'] = move_vals['asset_depreciated_value'] / asset_id.tax_today
        return move_vals

    def js_remove_outstanding_partial(self, partial_id):
        ''' Called by the 'payment' widget to remove a reconciled entry to the present invoice.

        :param partial_id: The id of an existing partial reconciled with the current invoice.
        '''
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        debit_move_id = partial.debit_move_id
        credit_move_id = partial.credit_move_id
        partial.unlink()
        if debit_move_id and credit_move_id:
            debit_move_id._compute_amount_residual_usd()
            credit_move_id._compute_amount_residual_usd()
        return True

    def generar_retencion_igtf(self):
        for rec in self:
            return {'name': _('Aplicar Retención IGTF'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'generar.igtf.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'domain': "",
                    'context': {
                            'default_invoice_id': rec.id,
                            'default_igtf_porcentage': rec.company_id.igtf_divisa_porcentage,
                            'default_tax_today': rec.currency_id_dif.inverse_rate,
                            'default_currency_id_dif': rec.currency_id_dif.id,
                            'default_currency_id_company': rec.company_id.currency_id.id,
                            'default_amount': rec.amount_residual_usd,
                        },
                    }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, date=None):
        company_currency = self.env.company.currency_id
        
        # Bloquea la conversión/recalculo si la SO está en moneda de la compañía.
        if any(order.currency_id == company_currency for order in self):
            return super(SaleOrder, self.with_context(skip_dual_currency_conversion=True))._create_invoices(grouped, final, date)
            
        return super()._create_invoices(grouped, final, date)