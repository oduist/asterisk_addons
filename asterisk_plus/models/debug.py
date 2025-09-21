from datetime import datetime, timedelta
from odoo import models, fields, api, _


class Debug(models.Model):
    _name = 'asterisk_plus.debug'
    _description = 'Asterisk Debug'
    _order = 'id desc'
    _rec_name = 'id'

    model = fields.Char()
    message = fields.Text()


    @api.model
    def vacuum(self, hours=24):
        """Cron job to delete debug data records.
        """
        expire_date = datetime.utcnow() - timedelta(hours=hours)
        records = self.env['asterisk_plus.debug'].search([
            ('create_date', '<=', expire_date.strftime('%Y-%m-%d %H:%M:%S'))
        ])
        records.unlink()
