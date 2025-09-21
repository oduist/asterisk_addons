# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2021
from odoo import models, fields


class HelpdeskCall(models.Model):
    _name = 'asterisk_plus.call'
    _inherit = 'asterisk_plus.call'

    ref = fields.Reference(selection_add=[
        ('helpdesk.ticket', 'Tickets')])

    def update_reference(self, **kwargs):
        res = super(HelpdeskCall, self).update_reference(**kwargs)
        if not res:
            return self.update_ticket_reference(**kwargs)

    def update_ticket_reference(self, **kwargs):
        try:
            if self.partner:
                tickets = self.env['helpdesk.ticket'].search([
                    ('partner_id', '=', self.partner.id)])
                for ticket in tickets:
                    if not ticket.stage_id.fold:
                        self.ref = ticket
                        self.env.cr.commit()
                        return True
        except Exception as e:
            logger.exception('update_ticket_reference error:')
