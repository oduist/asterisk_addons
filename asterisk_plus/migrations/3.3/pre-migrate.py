from odoo.tools.sql import rename_column
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    print('Migrating OdooPBX subscription UID...')
    instance_uid = env['ir.config_parameter'].get_param('odoopbx.instance_uid')
    if not instance_uid:
        database_uid = env['ir.config_parameter'].get_param('database.uuid')
        env['ir.config_parameter'].set_param('odoopbx.instance_uid', database_uid)
    if 'asterisk_plus_channel_data' in env:
        print('Dropping channel_key_uniq from channel_data...')
        env.cr.execute('''ALTER TABLE asterisk_plus_channel_data DROP 
            CONSTRAINT IF EXISTS asterisk_plus_channel_data_channel_key_uniq''')
    env.cr.execute('''ALTER TABLE asterisk_plus_channel DROP 
        COLUMN IF EXISTS "user"''')
