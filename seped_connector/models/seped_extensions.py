# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    seped_dc = fields.Float(
        string='SEPED Desc. Comercial (%)',
        help='Se sincroniza como dcomercial en SEPED.',
    )
    seped_di = fields.Float(
        string='SEPED Desc. Internet (%)',
        help='Se sincroniza como dinternet en SEPED.',
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    seped_da = fields.Float(
        string='SEPED Desc. Adicional (DA %)',
        help='Se sincroniza como da en SEPED.',
    )
    seped_da2 = fields.Float(
        string='SEPED Desc. Laboratorio (DA2 %)',
    )
    seped_dv = fields.Float(
        string='SEPED Desc. Volumen (DV %)',
    )
