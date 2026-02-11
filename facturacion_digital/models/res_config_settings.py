# -*- coding: utf-8 -*-
from odoo import api, fields, models, _ # type: ignore


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    #aplicar Factuta digital

    aplicar_fdigital = fields.Boolean(string='Activar Facturacion Digital', help='Cuando sea Verdadero, la facturacion digital estará disponible', related="company_id.aplicar_cdigital", readonly=False)

    #Datos Factura digital
    token_fdigital = fields.Char('Token', help="Token de seguridad suministrado por el proveedor de servicio", related="company_id.token_fdigital", readonly=False)
    url_fdigital = fields.Char('Url', help="URL suministrado por el proveedor de servicio", related="company_id.url_fdigital", readonly=False)

    
    
    @api.onchange('aplicar_fdigital')
    def _onchange_aplicar_fdigital(self):
        diarios = self.env['account.journal'].search([('company_id', '=', self.company_id.id)])
        for d in diarios:
            d.visible_facturad = self.aplicar_fdigital
            if self.aplicar_fdigital == False:
                d.facturaciond = False