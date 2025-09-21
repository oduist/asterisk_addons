# -*- coding: utf-8 -*
# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
from datetime import datetime, timedelta
import time
import json
import logging
from odoo import models, fields, api, tools, release, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from .settings import debug


logger = logging.getLogger(__name__)

MAX_EXTEN_LENGTH = 5

def convert_unixtime(ts):
    if ts:
        # Convert from unixtime to datetime.
        return datetime.utcfromtimestamp(ts).strftime(DATETIME_FORMAT)
    else:
        # Old Agent does not send EventTime so return now.
        return fields.Datetime.now()

# Helper model to keep channel data like call recording file path, etc...
class ChannelData(models.Model):
    _name = 'asterisk_plus.channel_data'
    _description = 'Channel Data'

    channel = fields.Many2one('asterisk_plus.channel', ondelete='cascade', required=False)
    call = fields.Many2one('asterisk_plus.call', ondelete='cascade')
    uniqueid = fields.Char(index=True)
    key = fields.Char(index=True, required=True)
    value = fields.Char()

    @api.model
    def vacuum(self, hours=24):
        """Cron job to delete channel data records.
        """
        expire_date = datetime.utcnow() - timedelta(hours=hours)
        records = self.env['asterisk_plus.channel_data'].search([
            ('create_date', '<=', expire_date.strftime('%Y-%m-%d %H:%M:%S'))
        ])
        records.unlink()


class Channel(models.Model):
    _name = 'asterisk_plus.channel'
    _rec_name = 'channel'
    _order = 'id desc'
    _description = 'Channel'

    #: Event time
    event_time = fields.Datetime()
    #: Call of the channel
    call = fields.Many2one('asterisk_plus.call', ondelete='cascade')
    #: Flag not to create a call (special cases when only channels are needed).
    no_call = fields.Boolean()
    #: Server of the channel. When server is removed all channels are deleted.
    server = fields.Many2one('asterisk_plus.server', ondelete='cascade', required=True)
    #: User who owns the channel
    user = fields.Many2one('res.users', ondelete='set null')
    #: Channel name. E.g. SIP/1001-000000bd.
    channel = fields.Char(index=True)
    #: Shorted channel to compare with user's channel as it is defined. E.g. SIP/1001
    channel_short = fields.Char(compute='_get_channel_short',
                                string=_('Chan'))
    #: Parent channel
    parent_channel = fields.Many2one('asterisk_plus.channel', compute='_get_parent_channel')
    #: Channel unique ID. E.g. asterisk-1631528870.0
    uniqueid = fields.Char(size=64, index=True)
    #: Linked channel unique ID. E.g. asterisk-1631528870.1
    linkedid = fields.Char(size=64, index=True, string='Linked ID')
    #: Channel context.
    context = fields.Char(size=80)
    # Connected line number.
    connected_line_num = fields.Char(size=80)
    #: Connected line name.
    connected_line_name = fields.Char(size=80)
    #: Channel's current state.
    state = fields.Char(size=80, string='State code')
    #: Channel's current state description.
    state_desc = fields.Char(size=256, string=_('State'))
    #: Channel extension.
    exten = fields.Char(size=32)
    #: Caller ID number.
    callerid_num = fields.Char(size=32, string='CallerID number')
    #: Caller ID name.
    callerid_name = fields.Char(size=32, string='CallerID name')
    #: System name.
    system_name = fields.Char(size=128)
    #: Channel's account code.
    accountcode = fields.Char(size=80)
    #: Channel's current priority.
    priority = fields.Char(size=4)
    #: Channel's current application.
    app = fields.Char(size=32, string='Application')
    #: Channel's current application data.
    app_data = fields.Char(size=512, string='Application Data')
    #: Channel's language.
    language = fields.Char(size=2)
    # Hangup event fields
    cause = fields.Char(index=True)
    cause_txt = fields.Char(index=True)
    hangup_date = fields.Datetime(index=True)
    timestamp = fields.Char(size=20)
    event = fields.Char(size=64)
    #: Flag to indicate if the channel is active
    is_active = fields.Boolean(index=True)
    is_primary = fields.Boolean(compute='_get_is_primary')
    channel_data = fields.One2many('asterisk_plus.channel_data', 'channel')

    ########################### COMPUTED FIELDS ###############################
    def _get_channel_short(self):
        # Makes SIP/1001-000000bd to be SIP/1001.
        for rec in self:
            if rec.channel:
                rec.channel_short = '-'.join(rec.channel.split('-')[:-1])
            else:
                rec.channel_short = False

    def _get_parent_channel(self):
        for rec in self:
            if rec.uniqueid != rec.linkedid:
                # Asterisk bound channels
                rec.parent_channel = self.search(
                    [('uniqueid', '=', rec.linkedid)], limit=1)
            else:
                rec.parent_channel = False

    def _get_is_primary(self):
        for rec in self:
            rec.is_primary = True if rec.uniqueid == rec.linkedid else False

    def set_inactive(self):
        for rec in self:
            rec.is_active = False

    @api.model
    def reload_channels(self, data=None):
        """Reloads channels list view.
        """
        auto_reload = self.env[
            'asterisk_plus.settings'].get_param('auto_reload_channels')
        if not auto_reload:
            return
        if data is None:
            data = {}
        if release.version_info[0] < 15:
            msg = {
                'action': 'reload_view',
                'model': 'asterisk_plus.channel'
            }
            self.env['bus.bus'].sendone('odoopbx_actions', json.dumps(msg))
        else:
            msg = {
                'model': 'asterisk_plus.channel'
            }
            self.env['bus.bus']._sendone(
                'odoopbx_actions',
                'reload_view',
                json.dumps(msg))

    def update_call_partner(self, channel, country=None):
        if channel.call.partner:
            debug(self, 'Partner already set.')
            return
        """
        Cases:
        1) Partner not set but there is a reference with partner set (click2call).
        2) Primary incoming call: search partner by callerid number.
        3) Primary outgoing call: search partner by exten.
        4) Secondary calls: don't find partners on secondary channels.
        """
        if not channel.is_primary:
            debug(self, 'Not setting partner on secondary channels.')
            return
        partner_id = False
        if channel.call.ref and getattr(channel.call.ref, 'partner_id', False):
            debug(self, 'Took partner from ref')
            partner_id = channel.call.ref.partner_id.id
        elif channel.call.direction == 'in':
            # For incoming call we take callerid to find partner.
            partner_id = channel.env['res.partner'].get_partner_by_number(
                channel.callerid_num, country=country)['id']
            debug(self, 'Partner %s from callerid number %s' % (partner_id, channel.callerid_num))
        else:
            # For outgoing calls we take exten
            partner_id = channel.env['res.partner'].get_partner_by_number(
                channel.exten, country=country)['id']
            debug(self, 'Partner %s from exten %s' % (partner_id, channel.exten))
        # Check if auto create partners is set & create partner.
        if channel.call.direction == 'in' and not partner_id and channel.env['asterisk_plus.settings'].get_param('auto_create_partners'):
            partner_number = channel.exten if channel.call.direction == 'out' else channel.callerid_num
            partner_id = channel.env['res.partner'].with_context(tracking_disable=True).sudo().create({
                'name': partner_number,
                'phone': partner_number,
            }).id
            debug(channel, 'Call {} auto create partner id {}'.format(channel.call.id, partner_id))
        if partner_id:
            debug(self, 'Setting partner %s for call %s' % (partner_id, channel.call.id))
            channel.call.partner = partner_id
        else:
            debug(self, 'Partner not found for call %s' % channel.call.id)

    def update_called_user(self, channel):
        # Secondary channel belonging to a user
        if channel.uniqueid != channel.call.uniqueid and channel.user:
            called_users = set(channel.call.called_users.mapped('id'))
            called_users.add(channel.user.id)
            channel.call.called_users = list(called_users)
            # Subscribe called user
            channel.call.message_subscribe(
                partner_ids=[channel.user.partner_id.id])
            # Notify user
            asterisk_user = channel.user.asterisk_users[:1]
            channel.call.notify_called_user(asterisk_user)

    ########################### AMI Event handlers ############################
    @api.model
    def on_ami_new_channel(self, event):
        """AMI NewChannel event is processed to create a new channel in Odoo.
        """
        debug(self, json.dumps(event))
        data = {
            'event': event['Event'],
            'server': self.env.user.asterisk_server.id,
            'channel': event['Channel'],
            'state': event['ChannelState'],
            'state_desc': event['ChannelStateDesc'],
            'callerid_num': event['CallerIDNum'],
            'callerid_name': event['CallerIDName'],
            'connected_line_num': event['ConnectedLineNum'],
            'connected_line_name': event['ConnectedLineName'],
            'language': event['Language'],
            'accountcode': event['AccountCode'],
            'priority': event['Priority'],
            'context': event['Context'],
            'exten': event['Exten'],
            'uniqueid': event['Uniqueid'],
            'linkedid': event['Linkedid'],
            'system_name': event.get('SystemName', 'asterisk'),
            'is_active': True,
            'event_time': convert_unixtime(event.get('EventTime')),
        }
        # Match the channel to a user
        asterisk_user = self.env[
            'asterisk_plus.user_channel'].get_user_channel(
                event['Channel'], self.env.user.asterisk_server).asterisk_user
        if asterisk_user:
            data['user'] = asterisk_user.user.id
            debug(self, 'Found PBX user %s for channel %s' % (asterisk_user.id, event['Channel']))
        # Search for an active channel with this Uniqueid (click2call originate).
        channel = self.env['asterisk_plus.channel'].search([
            ('is_active', '=', True),
            ('uniqueid', '=', event['Uniqueid'])], limit=1) # Some buggy Asterisk may send duplicate unique ids, so limit.
        # Create or update channel object
        if channel:
            debug(self, 'Found channel {} to update.'.format(event['Channel']))
            channel.write(data)
        else:
            channel = self.create(data)
            debug(channel, '{} create id: {}'.format(
                event['Channel'], channel.id
            ))
        # Commit changes ASAP for next Newstate events
        self.env.cr.commit()
        # Define country for number formatting
        country = (channel.user.partner_id.country_id.code or
            self.env.user.partner_id.country_id.code or None
        )
        debug(self, '{} id {} user {} country {}'.format(
            event['Channel'], channel.mapped('id'), channel.user.id, country
        ))
        if channel.no_call:
            # Special case not to create a call for the channel.
            self.reload_channels()
            return (channel.id, '{} Newchannel ACK'.format(event['Channel']))
        """
        Cases:
        1. Primary channel (Uniqueid = Linkedid) and channel user: 100% outgoing call.
        2. Secondary channel (Uniqueid != Linkedid) and channel user: 100% incoming call.
        3. Primary channel (Uniqueid = Linkedid) and no channel user:
            a) PBX User not mapped, outgoing call. In this case callerid <= MAX_EXTEN_LENGTH.
            b) Otherwise incoming call.
        4. Secondary channel (Uniqueid != Linkedid) and no channel user:
            a) Call has calling_user set from primary channel: outgoing call.
            b) PBX User not mapped, and exten <= MAX_EXTEN_LENGTH: incoming call
            c) Actually, anyway incoming call.
        """
        # Create a new call for the primary channel.
        if event['Uniqueid'] == event['Linkedid']:
            # Check if call already exists as originated from click2call.
            call = self.env['asterisk_plus.call'].search(
                [('is_active', '=', True), ('uniqueid', '=', event['Uniqueid'])], limit=1)
            if not call:
                # Define the call direction.
                if channel.user:
                    debug(self, 'Direction outgoing: primary channel with user')
                    direction = 'out'
                elif len(channel.callerid_num) <= MAX_EXTEN_LENGTH:
                    # PBX user not mapped but makes outgoing call.
                    debug(self, 'Direction outgoing, primary channel with len(callerid_num) <= %s' % MAX_EXTEN_LENGTH)
                    direction = 'out'
                else:
                    debug(self, 'Direction incoming, primary channel case 3b.')
                    direction = 'in'
                call = self.env['asterisk_plus.call'].create({
                    'direction': direction,
                    'uniqueid': event['Uniqueid'],
                    'calling_number': event['CallerIDNum'],
                    'callerid_name': event['CallerIDName'],
                    'calling_user': channel.user.id if direction == 'out' else False,
                    'called_number': event['Exten'],
                    'started': convert_unixtime(event.get('EventTime')),
                    'is_active': True,
                    'status': 'progress',
                    'server': self.env.user.asterisk_server.id,
                })
                debug(self, '{} spawn a new call: {}'.format(
                    event['Channel'], call.id
                ))
            else:
                debug(self, 'Found call %s for channel %s' % (call.id, event['Channel']))
        # Secondary channel, find the primary call.
        else:
            call = self.env['asterisk_plus.call'].search(
                [('uniqueid', '=', event['Linkedid'])], limit=1)
            if call:
                debug(self, '{} belongs to call: {}'.format(
                    event['Channel'], call.id))
            else:
                # Where is the primary channel and call!? We have to wait for it a while.
                self.env.cr.commit()
                for i in range(0,10):
                    call = self.env['asterisk_plus.call'].search(
                        [('uniqueid', '=', event['Linkedid'])], limit=1)
                    if not call:
                        debug(self, 'Call for {} not found, sleeping 0.1 sec'.format(event['Channel']), level='warning')
                        self.env.cr.commit()
                        time.sleep(.1)
                    else:
                        debug(self, 'Call for {} found after {} retries.'.format(event['Channel'], i))
                        break
                if not call:
                    debug(self, 'Call for {} not found, creating unlinked channel.'.format(event['Channel']), level='error')
                # Fix direction.
                if channel.user and channel.call and channel.call.direction == 'out':
                    # Case 2
                    debug(self, 'Direction change to incoming, secondary channel with PBX user.')
                    channel.call.direction = 'in'
                elif not channel.user and channel.call and channel.call.calling_user:
                    debug(self, 'Direction %s, not changing as calling user is set on primary channel' % channel.call.direction)
                else:
                    debug(self, 'Direction %s, not changing on secondary channel.' % channel.call.direction)
        channel.call = call
        # TODO: Remove me.
        ## Update the source number.
        #if channel.call and channel.call.calling_number != event['CallerIDNum']:
        #    channel.call.write({
        #        'calling_number': event['CallerIDNum'],
        #        'callerid_name': event['CallerIDName'],
        #    })
        self.env.cr.commit()
        # Update call partner
        self.update_call_partner(channel, country=country)
        # Update called users
        self.update_called_user(channel)
        # Commit again ASAP.
        self.env.cr.commit()
        # Update call reference
        if channel.is_primary and channel.call and not channel.call.ref:
            try:
                channel.call.update_reference(country=country)
            except Exception:
                logger.exception('Update call reference error:')
        # Reload channels
        self.reload_channels()
        return (channel.id, 'Call ID: {}'.format(channel.call.id))

    @api.model
    def on_ami_update_channel_state(self, event):
        """AMI Newstate event. Write call status and ansered time,
            create channel message and call event log records.
            Processed when channel's state changes.
        """
        debug(self, json.dumps(event))
        get = event.get
        data = {
            'server': self.env.user.asterisk_server.id,
            'channel': get('Channel'),
            'uniqueid': get('Uniqueid'),
            'linkedid': get('Linkedid'),
            'context': get('Context'),
            'connected_line_num': get('ConnectedLineNum'),
            'connected_line_name': get('ConnectedLineName'),
            'state': get('ChannelState'),
            'state_desc': get('ChannelStateDesc'),
            'exten': get('Exten'),
            'callerid_num': get('CallerIDNum'),
            'callerid_name': get('CallerIDName'),
            'accountcode': get('AccountCode'),
            'priority': get('Priority'),
            'timestamp': get('Timestamp'),
            'system_name': get('SystemName', 'asterisk'),
            'language': get('Language'),
            'event': get('Event'),
            'is_active': True,
            'event_time': convert_unixtime(event.get('EventTime')),
        }
        for _ in range(0,10):
            channel = self.env['asterisk_plus.channel'].search([
                ('is_active', '=', True),
                ('uniqueid', '=', get('Uniqueid'))], limit=1)
            if not channel:
                debug(self, '{} not found, sleeping 0.1 sec'.format(get('Channel')), level='warning')
                self.env.cr.commit()
                time.sleep(.1)
            else:
                break
        if not channel:
            debug(self, '{} not found, discard event'.format(get('Channel')), level='error')
            return (False, '{} not found, discard event.'.format(get('Channel')))
        debug(self, '{} channel id {}'.format(get('Channel'), channel.id))
        # Get call ID from the linked channel if it is not set
        if not channel.no_call and not channel.call and channel.uniqueid != channel.linkedid:
            for _ in range(0,10):
                linked_channel = self.env['asterisk_plus.channel'].search([
                    ('is_active', '=', True),
                    ('uniqueid', '=', channel.linkedid)], limit=1)
                if not linked_channel:
                    debug(channel,
                          '{} linked channel {} not found, sleeping 0.1 sec'.format(
                                channel.channel, channel.linkedid),
                                level='warning')
                    self.env.cr.commit()
                    time.sleep(.1)
                else:
                    break
            if linked_channel:
                data['call'] = linked_channel.call.id
                debug(channel,
                    '{} got call {} from the linked channel {}.'.format(
                    event['Channel'], data['call'], linked_channel.channel))
        channel.write(data)
        # There is no sense to go ahead if it's impossible to find the call
        if not channel.no_call and not channel.call:
            debug(channel, '{} id {} failed to match a call'.format(
                    event['Channel'], channel.id), level='error')
            return (channel.id, '{} failed to match a call'.format(event['Channel']))
        # Append an entry to call's events
        if channel.call:
            # Create call event.
            self.env['asterisk_plus.call_event'].create({
                'call': channel.call.id,
                'event': 'Channel {} status is {}'.format(
                    channel.channel_short, get('ChannelStateDesc')),
            })
            call_data = {}
            # Remove me.
            # Check for callerid update on calling leg.
            #if channel.call.uniqueid == channel.uniqueid and \
            #        channel.call.calling_number != channel.callerid_num:
            #    debug(self, 'Change callerid number from {} to {}.'.format(
            #        channel.call.calling_number, channel.callerid_num))
            #    call_data['calling_number'] = channel.callerid_num
            # The call is marked answered only when a secondary channel answers
            if (channel.call.uniqueid != channel.uniqueid): # 2nd leg.
                if channel.state_desc == 'Up':
                    call_data.update({
                            'status': 'answered',
                            'answered': convert_unixtime(event.get('EventTime'))})
                    user = self.env[
                        'asterisk_plus.user_channel'].get_user_channel(
                            event['Channel'], self.env.user.asterisk_server).user
                    if user:
                        call_data['answered_user'] = user.id
            debug(channel,'Call {} update: {}'.format(channel.call.id, call_data))
            channel.call.write(call_data)
        return (channel.id, '{} Newstate ACK'.format(event['Channel']))

    @api.model
    def on_ami_hangup(self, event):
        """AMI Hangup event.
        Returns tuple (channel.id, message)
        """
        debug(self, json.dumps(event))
        channel = self.env['asterisk_plus.channel'].search([
            ('is_active', '=', True),
            ('uniqueid', '=', event['Uniqueid'])], limit=1)
        if not channel:
            debug(self, 'Channel {} not found for hangup.'.format(event['Channel']))
            logger.warning('Channel {} not found for hangup.'.format(event['Channel']))
            return (None, '{} Hangup: not found'.format(event['Channel']))
        debug(self, 'Found {} channel(s) {}'.format(len(channel), event['Channel']))
        data = {
            'event': event['Event'],
            'channel': event['Channel'],
            'state': event['ChannelState'],
            'state_desc': event['ChannelStateDesc'],
            'callerid_num': event['CallerIDNum'],
            'callerid_name': event['CallerIDName'],
            'connected_line_num': event['ConnectedLineNum'],
            'connected_line_name': event['ConnectedLineName'],
            'language': event['Language'],
            'accountcode': event['AccountCode'],
            'context': event['Context'],
            'exten': event['Exten'],
            'priority': event['Priority'],
            'uniqueid': event['Uniqueid'],
            'linkedid': event['Linkedid'],
            'hangup_date': convert_unixtime(event.get('EventTime')),
            'cause': event['Cause'],
            'cause_txt': event['Cause-txt'],
            'is_active': False,
            'event_time': convert_unixtime(event.get('EventTime')),
        }
        channel.write(data)
        if channel.no_call:
            # No need to go futher to update call data.
            self.reload_channels()
            return (channel.id, '{} Hangup ACK'.format(event['Channel']))
        # Set call status by the primary channel
        if event['Uniqueid'] == event['Linkedid']:
            call_data = {
                'is_active': False,
                'ended': convert_unixtime(event.get('EventTime')),
            }
            # TODO: Remove me.
            # Check if callerid was changed on calling leg.
            #if channel.call and channel.call.calling_number != channel.callerid_num:
            #    debug(self, 'Change callerid number from {} to {}.'.format(
            #        channel.call.calling_number, channel.callerid_num))
            #    call_data['calling_number'] = channel.callerid_num
            if channel.call.status != 'answered':
                if channel.cause == '17':
                    call_data['status'] = 'busy'
                elif channel.cause == '19':
                    call_data['status'] = 'noanswer'
                # If the call had more then 1 channels but was never answered
                elif len(channel.call.channels) > 1:
                    call_data['status'] = 'noanswer'
                elif (channel.cause_txt == 'Normal Clearing' and
                        channel.state_desc == 'Up'):
                    call_data['status'] = 'ended'
                else:
                    call_data['status'] = 'failed'
            debug(self, 'Call {} update: {}'.format(
                channel.call.id, call_data))
            channel.call.write(call_data)
        # Create hangup event
        if channel.call:
            self.env['asterisk_plus.call_event'].create({
                'call': channel.call.id,
                'event': 'Channel {} hangup'.format(channel.channel_short),
            })
        # Commit changes before trying to get recording
        self.env.cr.commit()
        self.reload_channels()
        return (channel.id, '{} Hangup ACK'.format(event['Channel']))

    @api.model
    def on_ami_originate_response_failure(self, event):
        """AMI OriginateResponse event.
        """
        # This comes from Asterisk OriginateResponse AMI message when
        # call originate has been failed.
        if event['Response'] != 'Failure':
            logger.debug(self, 'Response', 'Ignoring OriginateResponse: %s', event)
            return False
        channel = self.env['asterisk_plus.channel'].search([
            ('is_active', '=', True),
            ('uniqueid', '=', event['Uniqueid'])], limit=1)
        if not channel:
            debug(self, 'Channel {} not found for OriginateResponse!'.format(event['Channel']))
            return False
        if channel.cause:
            # This is a response after Hangup so no need for it.
            return channel.id
        channel.write({
            'is_active': False,
            'cause': event['Reason'],  # 0
            'cause_txt': event['Response'],  # Failure
        })
        channel.call.write({'status': 'failed', 'is_active': False})
        reason = event.get('Reason')
        if reason == '0':
            reason = 'Calling user SIP phone is not registered or call declined.'
        # Notify user on a failed click to dial.
        if channel.call and channel.call.model and channel.call.res_id:
            self.env['asterisk_plus.settings'].odoopbx_notify(
                _('Call failed, reason: {0}').format(reason),
                notify_uid=channel.create_uid.id, warning=True)
        return channel.id

    @api.model
    def update_recording_filename(self, event):
        """AMI VarSet event.
        """
        debug(self, json.dumps(event))
        if event.get('Variable') == 'MIXMONITOR_FILENAME':
            file_path = event['Value']
            uniqueid = event['Uniqueid']
            channel = self.search([('uniqueid', '=', uniqueid)], limit=1)
            if channel:
                self.env['asterisk_plus.channel_data'].create({
                    'call': channel.call.id,
                    'channel': channel.id,
                    'key': 'recording_file_path',
                    'value': file_path,
                })
                return True
            else:
                logger.warning('Channel %s not found to update recording!', uniqueid)
        return False

    @api.model
    def vacuum(self, hours):
        """Cron job to delete channel records.
        """
        expire_date = datetime.utcnow() - timedelta(hours=hours)
        channels = self.env['asterisk_plus.channel'].search([
            ('create_date', '<=', expire_date.strftime('%Y-%m-%d %H:%M:%S'))
        ])
        channels.unlink()
