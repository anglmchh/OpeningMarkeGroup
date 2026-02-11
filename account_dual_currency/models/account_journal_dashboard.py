import ast
from babel.dates import format_datetime, format_date
from collections import defaultdict
from datetime import datetime, timedelta
import json
import random

from odoo import models, api, _, fields
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.release import version
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang

def group_by_journal(vals_list):
    res = defaultdict(list)
    for vals in vals_list:
        res[vals['journal_id']].append(vals)
    return res

class account_journal(models.Model):
    _inherit = "account.journal"

    is_exchange_diff_journal = fields.Boolean(
        string="Usar como Diario de Diferencial Cambiario",
        help="Si está activo, todos los asientos creados en este diario se registran con tasa 0."
    )

    @api.model
    def _fill_sale_purchase_dashboard_data(self, dashboard_data):
        # Primero, ejecutamos el super para que Odoo llene los datos base del dashboard
        super()._fill_sale_purchase_dashboard_data(dashboard_data)
        
        # 1. Separar los diarios en grupos de Venta y Compra
        sale_purchase_journals = self.filtered(lambda j: j.type in ('sale', 'purchase'))
        
        # CRÍTICO: Definir los recordsets de venta y compra para evitar NameError
        sale_journals = sale_purchase_journals.filtered(lambda j: j.type == 'sale')
        purchase_journals = sale_purchase_journals.filtered(lambda j: j.type == 'purchase')

        # 2. Manejo de caso vacío y obtención de la divisa de referencia
        if not sale_purchase_journals:
            return
            
        # Obtenemos la Divisa de Referencia (currency_id_dif) de forma segura
        currency_id_dif = sale_purchase_journals[0].company_id.currency_id_dif
        
        # El resto de la lógica utiliza las variables ya definidas: sale_journals, purchase_journals, currency_id_dif
        
        bills_field_list = [
            "account_move.journal_id",
            "(CASE WHEN account_move.move_type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * account_move.amount_total_usd AS amount_total",
            "(CASE WHEN account_move.move_type IN ('in_invoice', 'in_refund', 'in_receipt') THEN -1 ELSE 1 END) * account_move.amount_total_usd AS amount_total_company",
            "account_move.currency_id AS currency",
            "account_move.move_type",
            "account_move.invoice_date",
            "account_move.company_id",
        ]
        payment_field_list = [
            "account_move_line.journal_id",
            "account_move_line.move_id",
            "-account_move_line.amount_residual AS amount_total_company",
        ]
        # DRAFTS
        query, params = sale_purchase_journals._get_draft_bills_query().select(*bills_field_list)
        self.env.cr.execute(query, params)
        query_results_drafts = group_by_journal(self.env.cr.dictfetchall())

        # WAITING BILLS AND PAYMENTS
        query_results_to_pay = {}
        if purchase_journals:
            query, params = purchase_journals._get_open_payments_query().select(*payment_field_list)
            self.env.cr.execute(query, params)
            query_results_payments_to_pay = group_by_journal(self.env.cr.dictfetchall())
            for journal in purchase_journals:
                query_results_to_pay[journal.id] = query_results_payments_to_pay.get(journal.id, []) # Uso .get() para seguridad
        if sale_journals:
            query, params = sale_journals._get_open_bills_to_pay_query().select(*bills_field_list)
            self.env.cr.execute(query, params)
            query_results_bills_to_pay = group_by_journal(self.env.cr.dictfetchall())
            for journal in sale_journals:
                query_results_to_pay[journal.id] = query_results_bills_to_pay.get(journal.id, []) # Uso .get() para seguridad

        # LATE BILLS AND PAYMENTS
        late_query_results = {}
        if purchase_journals:
            query, params = purchase_journals._get_late_payment_query().select(*payment_field_list)
            self.env.cr.execute(query, params)
            late_payments_query_results = group_by_journal(self.env.cr.dictfetchall())
            for journal in purchase_journals:
                late_query_results[journal.id] = late_payments_query_results.get(journal.id, []) # Uso .get() para seguridad
        if sale_journals:
            query, params = sale_journals._get_late_bills_query().select(*bills_field_list)
            self.env.cr.execute(query, params)
            late_bills_query_results = group_by_journal(self.env.cr.dictfetchall())
            for journal in sale_journals:
                late_query_results[journal.id] = late_bills_query_results.get(journal.id, []) # Uso .get() para seguridad

        to_check_vals = {
            journal: (amount_total_signed_sum, count)
            for journal, amount_total_signed_sum, count in self.env['account.move']._read_group(
                domain=[('journal_id', 'in', sale_purchase_journals.ids), ('to_check', '=', True)],
                groupby=['journal_id'],
                aggregates=['amount_total_signed:sum', '__count'],
            )
        }

        sale_purchase_journals._fill_dashboard_data_count(dashboard_data, 'account.move', 'entries_count', [])
        for journal in sale_purchase_journals:
            # User may have read access on the journal but not on the company
            currency = journal.currency_id or self.env['res.currency'].browse(journal.company_id.sudo().currency_id.id)
            
            # Aseguramos que los diccionarios de resultados tengan entradas para este journal
            journal_id = journal.id
            draft_results = query_results_drafts.get(journal_id, [])
            waiting_results = query_results_to_pay.get(journal_id, [])
            late_results = late_query_results.get(journal_id, [])

            (number_waiting, sum_waiting) = self._count_results_and_sum_amounts(waiting_results, currency)
            (number_draft, sum_draft) = self._count_results_and_sum_amounts(draft_results, currency)
            (number_late, sum_late) = self._count_results_and_sum_amounts(late_results, currency)
            
            amount_total_signed_sum, count = to_check_vals.get(journal.id, (0, 0))
            
            # --- Formato y actualización del Dashboard (se asume que la lógica de USD es correcta) ---
            dashboard_data[journal.id].update({
                'number_to_check': count,
                'to_check_balance': currency.format(amount_total_signed_sum),
                'title': _('Bills to pay') if journal.type == 'purchase' else _('Invoices owed to you'),
                'number_draft': number_draft,
                'number_waiting': number_waiting,
                'number_late': number_late,
                
                # Conversión a USD utilizando currency_id_dif (Divisa de Referencia)
                'sum_draft': currency.format(sum_draft),
                # Nota: currency_id_dif.inverse_rate asume que la tasa está en formato 1/TASA, lo cual es común.
                'sum_draft_usd': currency_id_dif.format(sum_draft / currency_id_dif.inverse_rate), 

                'sum_waiting': currency.format(sum_waiting),
                'sum_waiting_usd': currency_id_dif.format(sum_waiting / currency_id_dif.inverse_rate),

                'sum_late': currency.format(sum_late),
                'sum_late_usd': currency_id_dif.format(sum_late / currency_id_dif.inverse_rate),

                'has_sequence_holes': journal.has_sequence_holes,
                'is_sample_data': dashboard_data[journal.id]['entries_count'],
            })
