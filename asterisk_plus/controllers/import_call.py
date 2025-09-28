import json
import base64
import logging
from odoo import http
from odoo.http import request, Response
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


class AsteriskPlusCallRecordImportController(http.Controller):

    @http.route('/asterisk_plus/create_call', type='json', auth='none', methods=['POST'], csrf=False)
    def create_asterisk_call(self, **kwargs):
        """
        Create a new record in asterisk_plus.call model
        """
        try:
            # Get the asterisk_plus.call model
            Call = request.env['asterisk_plus.call'].sudo()
            # Extract data from request
            data = request.jsonrequest
            data.update({'is_active': True})
            # Log the incoming data for debugging
            _logger.info("Received call creation request with data: %s", data)
            # Try to get partner.
            if data.get('direction') == 'in':
                # For incoming call we take callerid to find partner.
                partner_id = request.env['res.partner'].sudo().get_partner_by_number(
                    data.get('calling_number'))['id']
                _logger.info('Partner %s from calling_number %s' % (partner_id, data.get('calling_number')))
                data['partner'] = partner_id
            else:
                # For outgoing calls we take exten
                partner_id = request.env['res.partner'].sudo().get_partner_by_number(
                    data.get('called_number'))['id']
                _logger.info('Partner %s from called_number %s' % (partner_id, data.get('called_number')))
                data['partner'] = partner_id
            # Create the record with provided data
            # Since all params are optional, we pass whatever is provided
            call_record = Call.create(data)
            # "Hangup" the call
            call_record.is_active = False
            return {
                'success': True,
                'message': 'Call record created successfully',
                'call_id': call_record.id,
                'data': {
                    'id': call_record.id,
                    'name': call_record.display_name if hasattr(call_record, 'display_name') else str(call_record.id)
                }
            }

        except Exception as e:
            _logger.error("Error creating asterisk call record: %s", str(e))
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create call record'
            }


    @http.route('/asterisk_plus/upload_recording', type='http', auth='none', methods=['POST'], csrf=False)
    def upload_recording(self, **kw):
        """
        Upload a new recording file for a call identified by uniqueid.
        Expected parameters:
        - uniqueid: The unique identifier of the call
        - recording_file: The audio file to upload
        - filename (optional): Custom filename for the recording
        """
        try:
            # Get parameters
            uniqueid = kw.get('uniqueid')
            recording_file = kw.get('recording_file')
            filename = kw.get('filename')

            # Validate required parameters
            if not uniqueid:
                return self._json_response({
                    'success': False,
                    'error': 'uniqueid parameter is required'
                }, status=400)

            if not recording_file:
                return self._json_response({
                    'success': False,
                    'error': 'recording_file parameter is required'
                }, status=400)

            # Find the call by uniqueid
            call = request.env['asterisk_plus.call'].sudo().search([
                ('uniqueid', '=', uniqueid)
            ], limit=1)

            if not call:
                return self._json_response({
                    'success': False,
                    'error': 'No call found with uniqueid: {0}'.format(uniqueid)
                }, status=404)

            # Read the file content
            file_content = recording_file.read()
            if not file_content:
                return self._json_response({
                    'success': False,
                    'error': 'Uploaded file is empty'
                }, status=400)

            # Encode file content to base64
            file_data = base64.b64encode(file_content)

            # Set filename
            if not filename:
                filename = getattr(recording_file, 'filename', 'recording_{0}.wav'.format(uniqueid))

            # Check if recording already exists for this call
            existing_recording = request.env['asterisk_plus.recording'].sudo().search([
                ('call', '=', call.id)
            ], limit=1)

            if existing_recording:
                # Update existing recording
                existing_recording.write({
                    'recording_data': file_data,
                    'recording_filename': filename,
                    'file_path': filename,
                })
                recording = existing_recording
                action = 'updated'
            else:
                # Create new recording
                recording_vals = {
                    'uniqueid': uniqueid,
                    'call': call.id,
                    'recording_data': file_data,
                    'recording_filename': filename,
                    'file_path': filename,
                    'calling_number': call.calling_number,
                    'called_number': call.called_number,
                    'answered': call.answered,
                    'partner': call.partner.id if call.partner else False,
                    'calling_user': call.calling_user.id if call.calling_user else False,
                    'answered_user': call.answered_user.id if call.answered_user else False,
                }

                # Add channel if available
                if hasattr(call, 'channel') and call.channel:
                    recording_vals['channel'] = call.channel.id

                recording = request.env['asterisk_plus.recording'].sudo().create(recording_vals)
                action = 'created'

            _logger.info('Recording {0} for call {1}: {2}'.format(action, uniqueid, recording.id))

            return self._json_response({
                'success': True,
                'message': 'Recording {0} successfully'.format(action),
                'recording_id': recording.id,
                'call_id': call.id,
                'filename': filename
            })

        except ValidationError as e:
            _logger.error('Validation error uploading recording: {0}'.format(str(e)))
            return self._json_response({
                'success': False,
                'error': 'Validation error: {0}'.format(str(e))
            }, status=422)

        except Exception as e:
            _logger.error('Error uploading recording: {0}'.format(str(e)))
            return self._json_response({
                'success': False,
                'error': 'Internal server error: {0}'.format(str(e))
            }, status=500)

    def _json_response(self, data, status=200):
        """Helper method to return JSON response with proper headers"""
        headers = [
            ('Content-Type', 'application/json'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type'),
        ]
        return Response(
            json.dumps(data),
            status=status,
            headers=headers
        )
