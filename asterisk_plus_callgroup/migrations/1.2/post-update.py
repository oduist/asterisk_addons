from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for rec in env['asterisk_plus.callgroup'].search([]):
        if not rec.partner_id:
            partner = env['res.partner'].create({
                'name': rec.name,
                'mobile': rec.external_phone,
                'phone': rec.internal_phone,
            })
            rec.partner_id = partner
            print('Created partner link for call group {}'.format(rec.name))
