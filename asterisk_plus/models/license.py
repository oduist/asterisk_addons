# -*- coding: utf-8 -*-
"""
ODUIST PROPRIETARY LICENSE
Copyright (c) 2025 Oduist

This file contains license validation logic.
Modification is prohibited under Oduist Proprietary License.
See LICENSE and COPYRIGHT files for full terms.
"""

import logging
import uuid
from datetime import datetime, timedelta
from urllib.parse import urljoin

import jwt
import requests
from odoo import api, fields, models, release
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

PUBLIC_KEY_PARAM = "oduist_license.public_key"
ODUIST_MODULES = []


def api_call(url: str, request_data: dict) -> dict:
    """Perform a REST API call to the specified URL."""
    try:
        res = requests.post(url, json=request_data, timeout=30)
        data = res.json()
        if not res.ok:
            error_msg = data.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            return {"error": error_msg or f"License server error (HTTP {res.status_code})"}
        return data
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to license server. Please check your internet connection."}
    except requests.exceptions.Timeout:
        return {"error": "License server is not responding. Please try again later."}
    except requests.exceptions.RequestException as e:
        _logger.warning("License API request failed: %s", e)
        return {"error": "License server request failed. Please try again later."}
    except Exception as e:
        _logger.warning("Unexpected license API error: %s", e)
        return {"error": "Unexpected error contacting license server."}


class OduistLicense(models.Model):
    """
    License configuration and validation for Oduist modules.
    Single-record model storing license data and subscription preferences.
    """

    _name = "oduist.license"
    _description = "License Configuration"

    instance_uid = fields.Char(
        string="Instance UID",
        help="Unique identifier for this Odoo instance",
        readonly=True,
    )
    license_token = fields.Text(
        string="License Token",
        groups="base.group_erp_manager",
        help="JWT license token from oduist.com. Leave empty to use 30-day trial.",
    )
    registration_number = fields.Char(
        string="Registration Number",
        help="Registration number from license server",
    )
    subscribe_email = fields.Char(
        help="Email for subscription notifications"
    )
    subscribe_to_security_alerts = fields.Boolean(
        string="Subscribe to Critical Security Alerts",
        help="Receive immediate notifications regarding critical security vulnerabilities "
        "or urgent issues with your installed modules."
    )
    subscribe_to_onboarding = fields.Boolean(
        string="Subscribe to Personalized Onboarding Support",
        help="Receive step-by-step guidance for system setup. Usage data is analyzed "
        "to provide relevant tips and streamline your configuration process "
        "based on active features."
    )
    subscribe_to_updates = fields.Boolean(
        string="Subscribe to Product News & AI Tips and Tricks",
        help="Stay updated on new features, product releases, and the latest AI "
        "advancements within the Odoo ecosystem."
    )
    name = fields.Char(compute="_get_name", store=False)
    oduist_modules = fields.Many2many(
        "ir.module.module",
        string="Oduist Modules",
        compute="_compute_oduist_modules",
    )
    all_modules_purchased = fields.Boolean(
        compute="_compute_oduist_modules",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate instance_uid on first record creation"""
        for vals in vals_list:
            if not vals.get("instance_uid"):
                vals["instance_uid"] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, vals):
        """Update license status when agreement fields change"""
        res = super().write(vals)
        agreement_fields = {
            "subscribe_to_security_alerts",
            "subscribe_to_onboarding",
            "subscribe_to_updates",
            "subscribe_email",
        }
        if any(field in vals for field in agreement_fields):
            self.sudo().update_license_status(raise_exc=False)
        return res

    def _get_name(self):
        """Compute display name"""
        for rec in self:
            rec.name = "License Configuration"

    def _compute_oduist_modules(self):
        """Compute oduist modules and check if all are purchased"""
        for rec in self:
            modules = (
                self.env["ir.module.module"]
                .sudo()
                .search([("name", "in", ODUIST_MODULES), ("state", "=", "installed")])
            )
            rec.oduist_modules = modules
            rec.all_modules_purchased = all(
                m.oduist_module_purchased for m in modules
            )

    @api.model
    def get_param(self, param, default=False):
        """Get parameter value from single record. Creates record if not exists."""
        data = self.search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({})
        else:
            data = data[0]
        if not data:
            return default
        value = getattr(data, param, None)
        return value if value is not None else default

    @api.model
    def set_param(self, param, value):
        """Set parameter value in single record. Creates record if not exists."""
        data = self.search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({param: value})
        else:
            data[0].write({param: value})

    @api.model
    def open_license_form(self):
        """Open license configuration form."""
        rec = self.search([])
        if not rec:
            rec = self.sudo().with_context(no_constrains=True).create({})
        else:
            rec = rec[0]
        return {
            "type": "ir.actions.act_window",
            "res_model": "oduist.license",
            "res_id": rec.id,
            "name": "License Configuration",
            "views": [[self.env.ref(self._module + ".oduist_license_form").id, "form"]],
            "target": "current",
        }

    @api.model
    def _get_license_token(self):
        """Get license token from this record"""
        return self.sudo().get_param("license_token", default="")

    @api.model
    def _get_public_key(self):
        """Get public key from system parameters"""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(PUBLIC_KEY_PARAM, default="")
        )

    @api.model
    def validate_token(self, token):
        """
        Validate JWT token with RS256 algorithm.

        Returns:
            dict: Decoded payload if valid
            None: If token is invalid
        """
        if not token:
            return None

        public_key = self._get_public_key()
        if not public_key:
            _logger.warning("Public key not configured")
            return None

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_signature": True},
            )

            instance_uid = self.sudo().get_param("instance_uid")
            if payload.get("instance_hash") != instance_uid:
                _logger.warning(
                    "Token instance UID mismatch. Expected: %s, Got: %s",
                    instance_uid,
                    payload.get("instance_hash"),
                )
                return None

            return payload

        except jwt.ExpiredSignatureError:
            _logger.warning("Token signature expired")
            return None
        except jwt.InvalidTokenError as e:
            _logger.warning("Invalid token: %s", str(e))
            return None
        except Exception as e:
            _logger.error("Error validating token: %s", str(e))
            return None

    @api.model
    def is_trial_valid(self, module_name):
        module = (
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "=", module_name), ("state", "=", "installed")], limit=1)
        )
        if not module:
            return False, 0
        install_date = module.create_date or datetime.now() - timedelta(days=30)
        now = datetime.now()
        days_passed = (now - install_date).days
        days_left = 30 - days_passed
        is_valid = days_left > 0
        return is_valid, max(0, days_left)

    @api.model
    def get_license_status(self, module_name):
        token = self._get_license_token()
        if token:
            payload = self.validate_token(token)
            if payload:
                if payload.get("instance_type") == "demo":
                    return {"status": "demo"}
                purchased_modules = payload.get("purchased_modules", {})
                if module_name in purchased_modules:
                    module_info = purchased_modules[module_name]
                    order_id = module_info.get("order_id", "")
                    return {
                        "status": module_info.get("license_type"),
                        "order_id": order_id,
                    }
        is_valid, days_left = self.is_trial_valid(module_name)
        if is_valid:
            return {
                "status": "trial_active",
                "days_left": days_left,
            }
        else:
            return {
                "status": "trial_expired",
                "days_left": 0,
            }

    @api.model
    def get_oduist_license_banner(self):
        """
        Get license banner info for installed Oduist modules.
        Priority: trial_expired > trial_active > demo
        Returns: dict with module_name, status, message, type
        """
        installed_oduist_modules = (
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "in", ODUIST_MODULES), ("state", "=", "installed")])
            .mapped("name")
        )
        if not installed_oduist_modules:
            return None
        trial_expired_module = None
        trial_active_module = None
        demo_module = None
        for module_name in installed_oduist_modules:
            status = self.get_license_status(module_name)
            if status["status"] == "trial_expired" and not trial_expired_module:
                trial_expired_module = (module_name, status)
            elif status["status"] == "trial_active" and not trial_active_module:
                trial_active_module = (module_name, status)
            elif status["status"] == "demo" and not demo_module:
                demo_module = (module_name, status)
        selected_module = None
        if trial_expired_module:
            selected_module = trial_expired_module
            message_type = "danger"
            message = f"Oduist {selected_module[0].replace('_', ' ').title()}: Buy a license to continue"
        elif trial_active_module:
            selected_module = trial_active_module
            days_left = selected_module[1].get("days_left", 0)
            message_type = "warning" if days_left <= 7 else "info"
            message = f"Oduist {selected_module[0].replace('_', ' ').title()} Trial: {days_left} days remaining"
        elif demo_module:
            selected_module = demo_module
            message_type = "warning"
            message = f"Oduist {selected_module[0].replace('_', ' ').title()}: Demo License"
        if not selected_module:
            return None
        return {
            "module_name": selected_module[0],
            "status": selected_module[1]["status"],
            "message": message,
            "type": message_type,
        }

    @api.model
    def check_license(self, module_name, silent=True):
        status = self.sudo().get_license_status(module_name)
        is_valid = status["status"] != "trial_expired"
        if not is_valid and not silent:
            raise ValidationError("Module {} trial period has expired! Please buy a license to continue.".format(module_name))
        elif not is_valid and silent:
            _logger.warning("Module {} trial period has expired! Please buy a license to continue".format(module_name))
            return False
        else:
            return True

    @api.model
    def update_license_status(self, raise_exc=True):
        """
        Check license status with license server.
        Updates license_token, registration_number and subscription data.
        """
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("oduist_license_server")
        )
        if not base_url:
            raise ValidationError("License server URL not configured!")

        instance_uid = self.sudo().get_param("instance_uid")
        if not instance_uid:
            raise ValidationError("Instance UID not configured!")
        License = self.env["oduist.license"].sudo()
        ICP = self.env["ir.config_parameter"].sudo()

        subscribe_to_security_alerts = License.get_param("subscribe_to_security_alerts", default=False)
        subscribe_to_onboarding = License.get_param("subscribe_to_onboarding", default=False)
        subscribe_to_updates = License.get_param("subscribe_to_updates", default=False)

        # Get main company (first by ID)
        main_company = self.env["res.company"].search([], order="id", limit=1)
        country_code = main_company.country_id.code if main_company and main_company.country_id else None

        installed_modules = (
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "in", ODUIST_MODULES), ("state", "=", "installed")])
            .mapped("name")
        )

        request_data = {
            "instance_hash": instance_uid,
            "odoo_version": release.version_info[0],
            "installed_modules": installed_modules,
        }

        if country_code:
            request_data["country_code"] = country_code

        if subscribe_to_security_alerts:
            request_data["subscribe_to_security_alerts"] = True
        if subscribe_to_onboarding:
            request_data["subscribe_to_onboarding"] = True
        if subscribe_to_updates:
            request_data["subscribe_to_updates"] = True
        if subscribe_to_security_alerts or subscribe_to_onboarding or subscribe_to_updates:
            subscribe_email = License.get_param("subscribe_email", default="")
            if subscribe_email:
                request_data["subscribe_email"] = subscribe_email

        license_check_url = urljoin(base_url, "/license/v1/check")
        response = api_call(license_check_url, request_data)
        if response.get("error"):
            error_msg = response.get("error")
            _logger.debug('License check request failed: %s', error_msg)
            if raise_exc:
                raise ValidationError(error_msg)

        if not response and raise_exc:
            raise ValidationError("License check failed: empty response")
        if response.get("token"):
            License.set_param("license_token", response.get("token"))
            ICP.set_param(PUBLIC_KEY_PARAM, response.get("public_key"))
            token_data = self.validate_token(response.get("token"))
            if token_data and token_data.get("registration_number"):
                License.set_param(
                    "registration_number", token_data.get("registration_number")
                )
            modules_data = response.get("modules", {})
            for module_name, module_info in modules_data.items():
                if module_name in ODUIST_MODULES:
                    module = (
                        self.env["ir.module.module"]
                        .sudo()
                        .search(
                            [("name", "=", module_name), ("state", "=", "installed")],
                            limit=1,
                        )
                    )
                    if module:
                        vals = {}
                        if module_info.get("latest_version"):
                            vals["latest_version"] = module_info.get("latest_version")
                        if module_info.get("price") is not None:
                            vals["oduist_module_price"] = module_info.get("price")
                        if vals:
                            module.write(vals)
        else:
            error_msg = f"License check failed: {response}"
            _logger.warning(error_msg)
            if raise_exc:
                raise ValidationError(error_msg)

    def buy_all_licenses(self):
        """Initiate purchase process for all Oduist modules (excluding already purchased)."""
        token = self.sudo().get_param("license_token")
        if not token:
            self.update_license_status()
            token = self.sudo().get_param("license_token")
        token_data = self.validate_token(token) if token else None
        purchased_modules = token_data.get("purchased_modules", {}) if token_data else {}
        modules_to_buy = [m for m in ODUIST_MODULES if m not in purchased_modules]
        if not modules_to_buy:
            raise ValidationError("All modules are already purchased!")
        return self.buy_licenses(modules_to_buy)

    @api.model
    def buy_licenses(self, module_list):
        """
        Initiate purchase process for specified modules.

        Args:
            module_list: List of module names to purchase

        Returns:
            ir.actions.act_url action to open payment link
        """
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("oduist_license_server")
        )
        if not base_url:
            raise ValidationError("License server URL not configured!")

        instance_uid = self.sudo().get_param("instance_uid")
        if not instance_uid:
            raise ValidationError("Instance UID not configured!")
        # Get main company (first by ID)
        main_company = self.env["res.company"].search([], order="id", limit=1)
        country_code = main_company.country_id.code if main_company and main_company.country_id else None

        request_data = {
            "instance_hash": instance_uid,
            "modules": module_list,
        }

        if main_company:
            if main_company.vat:
                request_data["vat_number"] = main_company.vat
            if main_company.name:
                request_data["vat_company_name"] = main_company.name
            if main_company.street:
                request_data["vat_street"] = main_company.street
            if main_company.city:
                request_data["vat_city"] = main_company.city
            if main_company.state_id and main_company.state_id.name:
                request_data["vat_state"] = main_company.state_id.name
            if country_code:
                request_data["vat_country"] = country_code
            if main_company.zip:
                request_data["vat_postcode"] = main_company.zip

        license_buy_url = urljoin(base_url, "/license/v1/buy")
        response = api_call(license_buy_url, request_data)
        if response.get("error"):
            raise ValidationError(response.get("error"))

        if response and response.get("payment_link"):
            _logger.info(f"License buy result: {response}")
            return {
                "type": "ir.actions.act_url",
                "url": response["payment_link"],
                "target": "new",
            }
        else:
            error_msg = f"License buy failed: {response}"
            _logger.warning(error_msg)
            raise ValidationError(error_msg)
