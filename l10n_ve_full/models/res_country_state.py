# coding: utf-8
from odoo import fields, models

class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    municipality_id = fields.One2many('res.country.state.municipality', 'state_id', 'Municipios en este estado')