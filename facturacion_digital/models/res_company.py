# -*- coding: UTF-8 -*-
from odoo import models, fields, api, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
import re


class ResCompany(models.Model):
    _inherit = 'res.company'

    aplicar_cdigital = fields.Boolean(string='Facturacion Digital', 
                                       help='Cuando sea Verdadero, la facturacion digital estará disponible', 
                                       default=False, store=True)
    
    token_fdigital = fields.Char('Token', default='', store=True, readonly=False)
    url_fdigital = fields.Char('Url', default='', store=True, readonly=False)