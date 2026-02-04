# Context Storage Utilities for WhatsApp Task Bot
# Replaces Redis cache with database storage for persistent chat context

import frappe
import json


def get_context(phone_number):
    """Get context for a phone number
    
    Args:
        phone_number: User's phone number
        
    Returns:
        Dict with 'context_type' and 'context_data' keys, or None if not found
    """
    try:
        doc = frappe.get_doc("WhatsApp Chat Context", phone_number)
        context_data = doc.context_data
        if isinstance(context_data, str):
            context_data = json.loads(context_data)
        return {
            "context_type": doc.context_type,
            "context_data": context_data
        }
    except frappe.DoesNotExistError:
        return None


def set_context(phone_number, context_type, context_data):
    """Set context for a phone number (creates or updates)
    
    Args:
        phone_number: User's phone number
        context_type: Type of context (e.g., 'pending_tasks', 'guided_flow', 'task_list')
        context_data: Dict or list to store as JSON
    """
    
    
    # Serialize context_data if needed
    if not isinstance(context_data, str):
        context_data = json.dumps(context_data, default=str)
    
    try:
        # Check if record exists
        if frappe.db.exists("WhatsApp Chat Context", phone_number):
            doc = frappe.get_doc("WhatsApp Chat Context", phone_number)
            doc.context_type = context_type
            doc.context_data = context_data
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({
                "doctype": "WhatsApp Chat Context",
                "phone_number": phone_number,
                "context_type": context_type,
                "context_data": context_data
            })
            doc.insert(ignore_permissions=True)
        
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Error setting context for {phone_number}: {str(e)}", "Context Storage Error")
        raise


def clear_context(phone_number):
    """Clear context for a phone number
    
    Args:
        phone_number: User's phone number
    """
    try:
        frappe.delete_doc("WhatsApp Chat Context", phone_number, ignore_permissions=True)
        frappe.db.commit()
    except frappe.DoesNotExistError:
        pass


def has_context(phone_number, context_type=None):
    """Check if context exists for a phone number
    
    Args:
        phone_number: User's phone number
        context_type: Optional - if provided, checks if context matches this type
        
    Returns:
        True if context exists (and matches type if specified), False otherwise
    """
    try:
        doc = frappe.get_doc("WhatsApp Chat Context", phone_number)
        if context_type:
            return doc.context_type == context_type
        return True
    except frappe.DoesNotExistError:
        return False


def get_context_data(phone_number, context_type=None):
    """Get just the context_data for a phone number
    
    Args:
        phone_number: User's phone number
        context_type: Optional - if provided, only returns data if context matches this type
        
    Returns:
        The context_data (dict/list), or None if not found or type doesn't match
    """
    context = get_context(phone_number)
    if not context:
        return None
    
    if context_type and context["context_type"] != context_type:
        return None
    
    return context["context_data"]
