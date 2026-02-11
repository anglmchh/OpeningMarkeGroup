from odoo import http
from odoo.http import request

class BannerController(http.Controller):

    @http.route('/banner/status', type='json', auth='user')
    def banner_status(self):
        # Aquí podemos definir las condiciones bajo las cuales mostrar el banner.
        show_banner = True  # Este puede ser un parámetro de configuración, o una lógica personalizada.
        message = "Período anterior sin cerrar"  # Mensaje del banner

        # Ejemplo de condiciones para mostrar el banner
        if show_banner:
            return {
                'show_banner': True,
                'message': message,
            }
        return {
            'show_banner': False
        }
