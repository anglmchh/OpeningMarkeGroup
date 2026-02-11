from odoo import api, models, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class AccountFiscalLockChecker(models.Model):
    _name = 'account.fiscal.lock.checker'
    _description = 'Verificador de Bloqueo Fiscal'

    def _get_fiscal_lock_date(self):
        """Obtiene la fecha de bloqueo fiscal usando SQL directo"""
        self.env.cr.execute("""
            SELECT fiscalyear_lock_date 
            FROM account_change_lock_date
            ORDER BY id DESC
            LIMIT 1
        """)
        res = self.env.cr.fetchone()
        return res[0] if res else None

    def _notify_account_managers(self, title, message):
        """Envía notificaciones a todos los gerentes contables"""
        group = self.env.ref('account.group_account_manager')
        users = group.users
        notifications = []
        for user in users:
            notifications.append((user.partner_id, 'simple_notification', {
                'title': title,
                'message': message,
                'type': 'danger',
                'sticky': True
            }))
        self.env['bus.bus']._sendmany(notifications)

    @api.model
    def check_fiscal_lock_cron(self):
        """Método ejecutado por el Cron"""
        fiscal_lock_date = self._get_fiscal_lock_date()
        today = datetime.now().date()
        last_day_prev_month = today.replace(day=1) - timedelta(days=1)

        if not fiscal_lock_date or fiscal_lock_date < last_day_prev_month:
            message = _('''
                - Fecha de bloqueo fiscal: %s
                - Último día del mes anterior: %s
                - Antes de iniciar un nuevo período, debe cerrarse correctamente el período anterior.
                - Por favor, revise y complete el cierre correspondiente para evitar inconsistencias en los registros.
            ''') % (
                fiscal_lock_date.strftime('%d/%m/%Y') if fiscal_lock_date else _('No establecida'),
                last_day_prev_month.strftime('%d/%m/%Y')
            )
            self._notify_account_managers(_(' 🚨 ADVERTENCIA: PERIODO ANTERIOR SIN CERRAR'), message)
            _logger.warning("Notificación de bloqueo fiscal enviada a los gerentes contables.")