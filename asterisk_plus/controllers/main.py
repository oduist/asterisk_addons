# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
import json
import logging
import uuid
from odoo import http, SUPERUSER_ID, registry, release
from odoo.api import Environment
from werkzeug.exceptions import BadRequest, NotFound

logger = logging.getLogger(__name__)

MODULE_NAME = 'asterisk_plus'


def error_response(message):
    response = http.request.make_response(message)
    response.status_code = status=400
    response.headers.set('Content-Type', 'text/plain')
    return response


class AsteriskPlusController(http.Controller):

    def check_ip(self, db=None):
        if db:
            with registry(db).cursor() as cr:
                env = Environment(cr, SUPERUSER_ID, {})
                allowed_ips = env[
                    'asterisk_plus.settings'].sudo().get_param(
                    'permit_ip_addresses')
        else:
            allowed_ips = http.request.env[
                'asterisk_plus.settings'].sudo().get_param(
                'permit_ip_addresses')
        if allowed_ips:
            remote_ip = http.request.httprequest.remote_addr
            if remote_ip not in [
                    k.strip(' ') for k in allowed_ips.split(',')]:
                logger.warning('The IP address %s is not allowed to get caller name!', remote_ip)
                return '{} not allowed'.format(remote_ip)

    def _get_partner_by_number(self, db, number, country_code):
        # If db is passed init env for this db
        dst_partner_info = {'id': None}  # Defaults
        if db:
            try:
                with registry(db).cursor() as cr:
                    env = Environment(cr, SUPERUSER_ID, {})
                    dst_partner_info = env[
                        'res.partner'].sudo().get_partner_by_number(
                        number, country_code)
            except Exception:
                logger.exception('Db init error:')
                return 'Db error, check Odoo logs'
        else:
            dst_partner_info = http.request.env[
                'res.partner'].sudo().get_partner_by_number(
                number, country_code)
        return dst_partner_info

    @http.route('/asterisk_plus/get_caller_name', type='http', auth='none')
    def get_caller_name(self, **kw):
        db = kw.get('db')
        try:
            checked = self.check_ip(db=db)
            if checked is not None:
                return checked
            number = kw.get('number', '').replace(' ', '')  # Strip spaces
            country_code = kw.get('country') or False
            if not number:
                return 'Number not specified'
            dst_partner_info = self._get_partner_by_number(
                db, number, country_code)
            logger.info('get_caller_name number {} country {} id: {}'.format(
                number, country_code, dst_partner_info['id']))
            if dst_partner_info['id']:
                return dst_partner_info['name']
            return ''
        except Exception as e:
            logger.exception('Error:')
            if 'request not bound to a database' in str(e):
                return 'db not specified'
            elif 'database' in str(e) and 'does not exist' in str(e):
                return 'db does not exist'
            else:
                return 'Error'

    @http.route('/asterisk_plus/get_partner_manager', type='http', auth='none')
    def get_partner_manager(self, **kw):
        db = kw.get('db')
        try:
            checked = self.check_ip(db=db)
            if checked is not None:
                return checked
            number = kw.get('number', '').replace(' ', '')  # Strip spaces
            country_code = kw.get('country') or False
            exten = kw.get('exten', False)
            if not number:
                return 'Number not specified in request'
            dst_partner_info = self._get_partner_by_number(
                db, number, country_code)
            if dst_partner_info['id']:
                # Partner found, get manager.
                with registry(db).cursor() as cr:
                    env = Environment(cr, SUPERUSER_ID, {})
                    partner = env['res.partner'].sudo().browse(
                        dst_partner_info['id'])
                    if partner.user_id and partner.user_id.asterisk_users:
                        # We have user configured so let return his exten or channels
                        if exten:
                            result = partner.user_id.asterisk_users[0].exten
                        else:
                            originate_channels = [
                                k.name for k in partner.user_id.asterisk_users[0].channels
                                if k.originate_enabled]
                            result = '&'.join(originate_channels)
                        logger.info(
                            "Partner %s manager search result:  %s",
                            partner.id, result)
                        return result
            return ''
        except Exception as e:
            logger.exception('Error:')
            if 'request not bound to a database' in str(e):
                return 'db not specified'
            elif 'database' in str(e) and 'does not exist' in str(e):
                return 'db does not exist'
            else:
                return 'Error'

    @http.route('/asterisk_plus/get_caller_tags', auth='none', type='http')
    def get_caller_tags(self, **kw):
        db = kw.get('db')
        try:
            checked = self.check_ip(db=db)
            if checked is not None:
                return checked
            number = kw.get('number', '').replace(' ', '')  # Strip spaces
            country_code = kw.get('country') or False
            if not number:
                return 'Number not specified in request'
            dst_partner_info = self._get_partner_by_number(
                db, number, country_code)
            if dst_partner_info['id']:
                # Partner found, get manager.
                partner = http.request.env['res.partner'].sudo().browse(
                    dst_partner_info['id'])
                if partner:
                    return ','.join([k.name for k in partner.category_id])
            return ''
        except Exception as e:
            logger.exception('Error:')
            if 'request not bound to a database' in str(e):
                return 'db not specified'
            elif 'database' in str(e) and 'does not exist' in str(e):
                return 'db does not exist'
            else:
                return 'Error'

    @http.route('/asterisk_plus/ping', type='http', auth='none')
    def asterisk_ping(self, **kwargs):
        dbname = kwargs.get('dbname', 'odoopbx_15')
        with registry(dbname).cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            try:
                res = env['asterisk_plus.server'].browse(1).local_job(
                    fun='test.ping', sync=True)
                return http.Response('{}'.format(res))
            except Exception as e:
                logger.exception('Error:')
                return '{}'.format(e)

    @http.route('/asterisk_plus/asterisk_ping', type='http', auth='none')
    def ping(self, **kwargs):
        dbname = kwargs.get('dbname', 'demo_15.0')
        with registry(dbname).cursor() as cr:
            env = Environment(cr, http.request.env.ref('base.user_admin').id, {})
            try:
                res = env['asterisk_plus.server'].browse(1).ami_action(
                    {'Action': 'Ping'}, sync=True)
                return http.Response('{}'.format(res))
            except Exception as e:
                logger.exception('Error:')
                return '{}'.format(e)

    @http.route('/asterisk_plus/signup', auth='user')
    def signup(self):
        user = http.request.env['res.users'].browse(http.request.uid)
        email = user.partner_id.email
        if not email:
            return http.request.render('asterisk_plus.email_not_set')
        mail = http.request.env['mail.mail'].create({
            'subject': 'Asterisk calls subscribe request',
            'email_from': email,
            'email_to': 'odooist@gmail.com',
            'body_html': '<p>Email: {}</p>'.format(email),
            'body': 'Email: {}'.format(email),
        })
        mail.send()
        return http.request.render('asterisk_plus.email_sent',
                                   qcontext={'email': email})

    @http.route('/%s/transcript/<int:rec_id>' % MODULE_NAME, methods=['POST'], type='json',
                auth='public', csrf=False)
    def upload_transcript(self, rec_id):
        # Public method protected by the one-time transcription token.
        data = json.loads(http.request.httprequest.get_data(as_text=True))
        rec = http.request.env['%s.recording' % MODULE_NAME].sudo().search([
            ('id', '=', rec_id), ('transcription_token', '!=', False),
            ('transcription_token', '=', data['transcription_token'])
        ])
        if not rec:
            logger.warning('Transcription token %s not found for recording %s',
                data['transcription_token'], rec_id)
            return error_response('Bad taken')
        rec.update_transcript(data)        
        return True

    @http.route('/asterisk_plus/agent', type='http', auth='none')
    def init_agent(self, **kw):
        db = kw.get('db')
        if db:
            try:
                with registry(db).cursor() as cr:
                    env = Environment(cr, SUPERUSER_ID, {})
                    return self._initialize_server(env)
            except Exception as e:
                if 'does not exist' in str(e):
                    logger.error('Database %s does not exist!', db)
                    return error_response('Database does not exist!')
                raise
        else:
            try:
                env = http.request.env
                return self._initialize_server(env)
            except Exception as e:
                if 'request not bound to a database' in str(e):
                    logger.error('You must specify db parameter!')
                    return error_response('You must specify db paramater!')
                raise

    def _initialize_server(self, env):
        # Check if Server is already initialized.
        server = env.ref('asterisk_plus.default_server').sudo()
        if server.agent_initialized:
            return error_response('Agent is already initialized.')
        if not server.permit_agent_initialization:
            return error_response('Agent initialization is not permitted!')
        # Check subscription
        is_subscribed = env['asterisk_plus.settings'].sudo().get_param('is_subscribed')
        is_registered = env['asterisk_plus.settings'].sudo().get_param('is_registered')
        if not is_registered or not is_subscribed:
            return error_response('Please register and subscribe from the Odoo first!')
        # Get API URL and key and pass to the agent
        data = {
            'api_url': env['asterisk_plus.settings'].sudo().get_param('api_url'),
            'api_key': env['asterisk_plus.settings'].sudo().get_param('api_key'),
            'instance_uid': env['asterisk_plus.settings'].sudo().get_param('instance_uid'),
        }
        server.write({
            'agent_initialized': True,
            'permit_agent_initialization': False,
        })
        # Set initialized flag to disable future requests.
        logger.info('Agent initialization complete.')
        return http.request.make_response(json.dumps(data))

    @http.route('/asterisk_plus/sip_peers', methods=['GET'], auth='public')
    def get_sip_peers(self):
        """
        Public method protected by the server's security_token
        Generate part of SIP config for Odoo PBX Users
        test:
        curl -v -H "x-security-token: STOKEN" http://ODOO_URL/asterisk_plus/sip_peers
        """
        logger.info('get_sip_conf: Request for SIP conf')
        # The only params available for change is agent_url and subscription server
        token = http.request.httprequest.headers.get("x-security-token")
        if not token:
            return error_response('; No token!\n')
        server = http.request.env['asterisk_plus.server'].sudo().search(
            [('security_token', '=', token)])
        if not server:
            return error_response('; Bad token!\n')
        if not server.generate_sip_peers:
            return error_response('; Server has generate_sip_peers setting disabled!\n')
        try:
            return server.get_sip_peers()
        except Exception as e:
            logger.exception('Cannot generate SIP peers:')
            return error_response('; Error generating peers, check Odoo log!\n')


    @http.route('/asterisk_plus/get_user_data_by_did', auth='public', methods=['GET'])
    def get_user_data_by_did(self, **kwargs):
        """
        Public method protected by the server's security_token
        Method for getting info for inbound routing
        test:
        curl -v -H "x-security-token: STOKEN" https://${ODOO_URL}/asterisk_plus/get_user_data_by_did?did=${DID}
        """
        logger.info('get_user_data_by_did: Request for Incoming roting')

        # check odoo token
        token = http.request.httprequest.headers.get("x-security-token")
        # Retrieve parameters from the HTTP request
        did = kwargs.get('did', False)

        if not token:
            return error_response('; No token!\n')
        if not did:
            return error_response('; Please provide DID\n')

        server = http.request.env['asterisk_plus.server'].sudo().search(
            [('security_token', '=', token)])
        if not server:
            return error_response('; Bad token!\n')
        # Check for + and prepend if absent.
        if not did.startswith('+'):
            did = '+' + did
        # Remove spaces
        did = did.replace(' ', '')
        dial_data = {}
        users = http.request.env['res.users'].sudo().search(
            [('phone_normalized', '=', did)])
        if not users:
            logger.info('User for number "%s" not found!', did)
            return error_response('; No user for this did found')
        elif len(users) == 1:
            # One user
            user = users[0]
            dial_data["mobile"] = user.mobile_normalized or 'False'
            dial_data["dialstring"] = "False"
            if user.asterisk_users.channels:
                channels = []
                for ch in user.asterisk_users.channels:
                    channels.append(ch.name)
                dial_data["dialstring"] = '&'.join(channels)
        else:
            # More users, we don't return mobile numbers in this case.
            dial_data["mobile"] = 'False'
            dial_data["dialstring"] = "False"
            channels = []
            for user in users:
                if user.asterisk_users.channels:
                    for ch in user.asterisk_users.channels:
                        channels.append(ch.name)
            dial_data["dialstring"] = '&'.join(channels)
        logger.info('Dial data %s by number "%s".', dial_data, did)
        return json.dumps(dial_data)

    @http.route('/asterisk_plus/get_outbound_callerid_by_channel', auth='public', methods=['GET'])
    def get_outbound_callerid_by_channel(self, **kwargs):
        """
        Public method protected by the server's security_token
        Method for getting info for outbound callerid
        test:
        curl -v -H "x-security-token: STOKEN" https://${ODOO_URL}/asterisk_plus/get_outbound_callerid_by_channel?channel=${CHANNEL}
        """
        logger.info('get_outbound_callerid_by_channel: Request for Setting outbound callerid')

        # check odoo token
        token = http.request.httprequest.headers.get("x-security-token")
        # Retrieve parameters from the HTTP request
        req_channel = kwargs.get('channel', False)

        if not token:
            logger.error('No token passed!')
            return ''
        if not req_channel:
            logger.error('No channel passed!')
            return ''

        server = http.request.env['asterisk_plus.server'].sudo().search(
            [('security_token', '=', token)])
        if not server:
            logger.error('Server not found by token!')
            return ''
        
        user_channel = http.request.env['asterisk_plus.user_channel'].sudo().search(
            [('name', '=', req_channel)])
        if not user_channel:
            logger.info('PBX user for channel "%s" not found!', req_channel)
            return ''
        callerid_num = user_channel.asterisk_user.user.phone_normalized
        logger.info('Found callerid number %s by channel "%s".', callerid_num, req_channel)
        return callerid_num

    @http.route('/asterisk_plus/voicemail.conf', auth='public', methods=['GET'])
    def get_voicemail_conf(self, **kwargs):
        logger.info('get_voicemail_conf: Request for Voicemail conf')
        # The only params available for change is agent_url and subscription server
        token = http.request.httprequest.headers.get("x-security-token")
        if not token:
            return error_response('; No token!\n')
        server = http.request.env['asterisk_plus.server'].sudo().search(
            [('security_token', '=', token)])
        if not server:
            return error_response('; Bad token!\n')
        try:
            return server.generate_voicemail_conf()
        except Exception as e:
            logger.exception('Cannot get voicemail.conf:')
            return error_response('; Error getting voicemail, check Odoo log!\n')


