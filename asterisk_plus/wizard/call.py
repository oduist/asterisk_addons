# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
import logging
from odoo import fields, models, api, _

logger = logging.getLogger(__name__)


class CallsWizard(models.TransientModel):
    _name = 'asterisk_plus.call_wizard'
    _description = 'Call History Wizard'

    start_date = fields.Datetime(required=True)
    end_date = fields.Datetime(required=True,
                               default=lambda self: fields.Datetime.now())
    from_user = fields.Many2one('res.users', domain=[('share', '=', False)])
    to_user = fields.Many2one('res.users', domain=[('share', '=', False)])
    to_partner = fields.Many2one('res.partner')
    from_partner = fields.Many2one('res.partner')
    call_status = fields.Selection(selection=[
         ('noanswer', 'No Answer'), ('answered', 'Answered'),
         ('busy', 'Busy'), ('failed', 'Failed'),
         ('progress', 'In Progress')], default='answered')
    # Fields
    src = fields.Boolean(default=True, string=_("Source"))
    dst = fields.Boolean(default=True, string=_("Destination"))
    src_user = fields.Boolean(string=_("From User"))
    dst_user = fields.Boolean(string=_("To User"))
    partner = fields.Boolean(default=True, string=_("Partner"))
    clid = fields.Boolean(default=True, string=_("Caller ID"))
    started = fields.Boolean(default=True)
    ended = fields.Boolean()
    duration = fields.Boolean(string=_("Call Duration"), default=True)
    disposition = fields.Boolean(default=True)

    def submit(self):
        self.ensure_one()
        calls = self.env['asterisk_plus.call'].search([
                                        ('started', '>=', self.start_date),
                                        ('started', '<=', self.end_date)])
        if self.from_user:
            calls = calls.filtered(lambda r: r.calling_user == self.from_user)
        if self.to_user:
            calls = calls.filtered(lambda r: r.answered_user == self.to_user)
        if self.to_partner:
            calls = calls.filtered(
                lambda r: r.partner == self.to_partner and not r.calling_user)
        if self.from_partner:
            calls = calls.filtered(
                lambda r: r.partner == self.from_partner and not r.answered_user)
        if self.call_status:
            calls = calls.filtered(
                lambda r: r.status == self.call_status)
        data = {
            'ids': [k.id for k in calls],
            'title': _('Calls from {} to {}').format(
                                            self.start_date, self.end_date),
            'fields': {
                'calling_number': self.src,
                'called_number': self.dst,
                'calling_user': self.src_user,
                'answered_user': self.dst_user,
                'partner': self.partner,
                'calling_name': self.clid,
                'started': self.started,
                'ended': self.ended,
                'duration': self.duration,
                'status': self.call_status,
                }
        }
        return self.env.ref(
            'asterisk_plus.calls_report_action').report_action(self,
                                                                data=data)
