# Menu and Navigation Handlers
# Handles menu triggers, status filter triggers, and navigation

import frappe
import json

from ..whatsapp_utils import send_reply, send_typing_indicator, send_interactive_message
from ..user_utils import get_user_by_phone
from ..date_utils import get_days_text
from .task_handlers import send_task_list_with_numbers

# Constants
MENU_TRIGGERS = ['menu', 'help', 'start']

STATUS_FILTER_TRIGGERS = {
    'not started': 'Not Started',
    'in progress': 'In Progress',
    'on hold': 'On Hold'
}

STATUS_DISPLAY = {
    "Not Started": "⚫ Not Started",
    "In Progress": "🔵 In Progress",
    "Completed": "🟢 Completed",
    "On Hold": "🟠 On Hold"
}


def get_status_display(status):
    """Get display text with emoji for status"""
    return STATUS_DISPLAY.get(status, status)


def handle_menu_trigger(message, from_number, whatsapp_account):
    """Handle menu/help/start trigger to show main menu buttons"""
    if message.strip().lower() not in MENU_TRIGGERS:
        return False
    
    send_typing_indicator(from_number, whatsapp_account)
    
    buttons = [
        {"id": "MENU_ADD_TASK", "title": "➕ Add Tasks"},
        {"id": "MENU_MY_TASKS", "title": "📋 My Tasks"}
    ]
    
    message_body = (
        "👋 *Welcome to Task Manager*\n\n"
        "What would you like to do?\n\n"
        "You can also type:\n"
        "• `my tasks` - View your tasks\n"
        "• `add tasks` - Create new tasks\n"
        "• `not started` / `in progress` / `on hold` - Filter by status"
    )
    
    send_interactive_message(from_number, message_body, buttons, whatsapp_account)
    return True


def handle_status_filter_trigger(message, from_number, whatsapp_account):
    """Handle status filter triggers like 'not started', 'in progress', 'on hold'"""
    message_lower = message.strip().lower()
    
    if message_lower not in STATUS_FILTER_TRIGGERS:
        return False
    
    status = STATUS_FILTER_TRIGGERS[message_lower]
    
    current_user = get_user_by_phone(from_number)
    if not current_user:
        send_reply(
            from_number,
            "❌ Your phone number is not linked to any user account.",
            whatsapp_account
        )
        return True
    
    send_filtered_tasks(from_number, current_user["name"], status, whatsapp_account)
    return True


def send_filtered_tasks(to_number, assigned_to, status, whatsapp_account):
    """Send tasks filtered by status"""
    from frappe.utils import getdate, today
    
    send_typing_indicator(to_number, whatsapp_account)
    
    try:
        today_date = getdate(today())
        
        tasks = frappe.get_all(
            "Sprint Board",
            filters={
                "status": status,
                "assigned_to": assigned_to
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        if not tasks:
            send_reply(
                to_number,
                f"✅ No tasks with status *{get_status_display(status)}*",
                whatsapp_account
            )
            return
        
        task_list = []
        for task in tasks:
            days_text = get_days_text(task.deadline, today_date)
            
            task_list.append({
                "task_id": task.name,
                "task_title": task.task_name,
                "days_text": days_text,
                "status": task.status,
                "deadline": task.deadline
            })
        
        # Sort by deadline
        def sort_key(t):
            if not t["deadline"]:
                return "9999-99-99"
            return str(getdate(t["deadline"]))
        
        task_list.sort(key=sort_key)
        
        send_task_list_with_numbers(to_number, task_list, whatsapp_account, f"Tasks - {get_status_display(status)}")
        
    except Exception as e:
        frappe.log_error(f"Error sending filtered tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)
