from odoo import fields, models, api


class User(models.Model):
    _inherit = 'asterisk_plus.user_channel'

    @api.model
    def create(self, vals):
        # Create Yeastar user context.
        default_context = self.env['asterisk_plus.settings'].sudo().get_param(
            'originate_context', 'from-internal')
        if default_context == vals.get('originate_context'):
            # Replace to DLPN_DialPlan1000
            user = self.env['asterisk_plus.user'].browse(vals['asterisk_user'])
            vals['originate_context'] = 'DLPN_DialPlan{}'.format(user.exten)
        return super().create(vals)
