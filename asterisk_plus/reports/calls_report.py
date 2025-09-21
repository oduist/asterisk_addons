# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
from datetime import timedelta
import logging
import time
from odoo import api, models
from dateutil.parser import parse
from odoo.exceptions import UserError


logger = logging.getLogger(__name__)


class CallsReport(models.AbstractModel):
    _name = 'report.asterisk_plus.calls_report'
    _description = 'Call Report'

    def _get_report_values(self, docids, data=None):
        if docids:
            # Call from context menu
            data = {}
            docs = self.env['asterisk_plus.call'].browse(docids)
            fields = {
                'calling_number': True,
                'called_number': True,
                'calling_user': False,
                'answered_user': False,
                'partner': True,
                'calling_name': True,
                'started': True,
                'ended': False,
                'duration': True,
                'status': True,
            }
        else:
            docs = self.env['asterisk_plus.call'].browse(data['ids'])
            fields = data.get('fields')
        docargs = {
            'doc_ids': [k.id for k in docs],
            'doc_model': 'asterisk_plus.call',
            'docs': docs,
            'time': time,
            'title': data.get('title'),
            'fields': fields,
            'total_calls': len(docs),
            'total_duration': str(
                timedelta(seconds=sum(docs.mapped('duration')))),
        }
        return docargs
