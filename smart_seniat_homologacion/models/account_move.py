# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command # type: ignore
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning # type: ignore


class AccountMove(models.Model):
    _inherit = 'account.move'


    # def action_post(self):
    #     if self.correlative == False:
    #         sequence =  self.env['ir.sequence'].search([('name', '=', 'Secuencia Numero de Control')])
    #         nro_interno_control = str(sequence.number_next).zfill(8)
    #         self.correlative = nro_interno_control
            
    #     res = super().action_post()
        
    #     if res:
    #         sequence.number_next_actual = sequence.number_next_actual + sequence.number_increment
    
    def action_unlink_custom(self):
        action = None
        for record in self:
            if record.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                action = self.env.ref('account.action_move_out_invoice_type').read()[0]
            elif record.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
                action = self.env.ref('account.action_move_in_invoice_type').read()[0]
            record.unlink()
        return action

    def ejecutar_nota_de_debito(self):
        self.ensure_one()
        return self.action_debit_note()

