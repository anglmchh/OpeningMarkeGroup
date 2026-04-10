from odoo import models, fields, api

class LgcPartCategory(models.Model):
    _name = 'lgc.part.category'
    _description = 'Categoría de Autopartes'
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char('Nombre', required=True)
    complete_name = fields.Char('Nombre Completo', compute='_compute_complete_name', recursive=True, store=True)
    parent_id = fields.Many2one('lgc.part.category', string='Categoría Padre', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('lgc.part.category', 'parent_id', string='Categorías Hijas')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

class LgcPartsCatalog(models.Model):
    _name = 'lgc.parts.catalog'
    _description = 'Catálogo de Autopartes Inteligente'
    _order = 'confidence desc, id desc'

    # Vehículo
    vehicle_make = fields.Char(string='Marca Vehículo', default='Toyota', required=True, index=True)
    vehicle_model = fields.Char(string='Modelo', required=True, index=True)
    vehicle_year = fields.Integer(string='Año', index=True)
    vehicle_origin = fields.Char(string='Origen (Región)')
    vehicle_trim = fields.Char(string='Versión / Trim', help='Ej: Automático XL, 4WD, etc.')

    # Pieza
    part_type = fields.Char(string='Tipo de Pieza (Libre)', help='Ej: Pastillas de freno')
    category_id = fields.Many2one('lgc.part.category', string='Categoría', required=True, index=True)
    brand = fields.Char(string='Marca Pieza', help='Ej: Denso, KYB, Toyota Genuine')
    part_number = fields.Char(string='Número de Parte', required=True, index=True)
    product_id = fields.Many2one('product.product', string='Producto Asociado')
    
    # Multimedia y Comercial
    image_1920 = fields.Image("Imagen", max_width=1920, max_height=1920)
    image_128 = fields.Image("Miniatura", related="image_1920", max_width=128, max_height=128, store=True)
    
    list_price = fields.Float(string='Precio de Venta', compute='_compute_list_price', store=True, readonly=False)

    # Metadatos del Catálogo
    source = fields.Selection([
        ('conversation', 'Conversación (IA)'),
        ('supervisor', 'Supervisor'),
        ('epc', 'Toyota EPC'),
    ], string='Fuente de Datos', default='supervisor', required=True)
    
    confidence = fields.Integer(string='Nivel de Confianza (%)', default=100)
    times_confirmed = fields.Integer(string='Veces Confirmado', default=0)
    
    active = fields.Boolean(default=True)

    @api.depends('product_id', 'product_id.list_price')
    def _compute_list_price(self):
        for record in self:
            if record.product_id:
                record.list_price = record.product_id.list_price
            elif not record.list_price:
                record.list_price = 0.0

    @api.depends('part_number', 'part_type', 'vehicle_model', 'vehicle_year')
    def _compute_display_name(self):
        for record in self:
            year_str = f" {record.vehicle_year}" if record.vehicle_year else ""
            record.display_name = f"[{record.part_number}] {record.part_type or record.category_id.name} - {record.vehicle_model}{year_str}"
