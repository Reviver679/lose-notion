# WhatsApp API Utilities for Task Bot
# Handles all WhatsApp Cloud API interactions

import frappe
import requests
import json


def get_whatsapp_api_credentials(whatsapp_account):
    """Get WhatsApp API credentials from account doctype"""
    try:
        account = frappe.get_doc("WhatsApp Account", whatsapp_account)
        return {
            "access_token": account.get_password("token") if hasattr(account, 'token') else account.token,
            "phone_number_id": account.phone_id,
            "api_url": f"https://graph.facebook.com/v18.0/{account.phone_id}/messages"
        }
    except Exception:
        return None


def mark_as_read(message_id, whatsapp_account):
    """Mark incoming message as read (blue ticks) via WhatsApp Cloud API"""
    if not message_id:
        return
    
    try:
        creds = get_whatsapp_api_credentials(whatsapp_account)
        if not creds:
            return
        
        headers = {
            "Authorization": f"Bearer {creds['access_token']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        requests.post(creds['api_url'], headers=headers, json=payload, timeout=5)
    except Exception as e:
        frappe.log_error(f"Failed to mark as read: {str(e)}", "WhatsApp API Error")


def send_typing_indicator(to_number, whatsapp_account):
    """Show typing indicator to user via WhatsApp Cloud API
    
    NOTE: The typing indicator API is not yet working. 
    This is a placeholder for future implementation when the correct
    API format is confirmed with your WhatsApp Business setup.
    """
    # TODO: Implement typing indicator when API format is confirmed
    pass


def send_reply(to_number, message, whatsapp_account):
    """Send a text reply message with typing indicator"""
    try:
        send_typing_indicator(to_number, whatsapp_account)
        
        wa_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": to_number,
            "message": message,
            "content_type": "text",
            "whatsapp_account": whatsapp_account
        })
        wa_msg.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to send reply: {str(e)}", "Task Alert Error")


def send_interactive_message(to_number, message_body, buttons, whatsapp_account):
    """Send an interactive message with buttons
    
    Args:
        to_number: Recipient phone number
        message_body: Message text
        buttons: List of button dicts with 'id' and 'title' keys
        whatsapp_account: WhatsApp account name
    """
    try:
        send_typing_indicator(to_number, whatsapp_account)
        
        wa_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": to_number,
            "message": message_body,
            "content_type": "interactive",
            "buttons": json.dumps(buttons),
            "whatsapp_account": whatsapp_account
        })
        wa_msg.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to send interactive message: {str(e)}", "Task Alert Error")
