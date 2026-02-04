# Sprint Board WhatsApp Integration
# Main router for WhatsApp task management bot
#
# This file acts as the entry point and routes messages to appropriate handlers.
# All logic is implemented in the handlers/ modules.

import frappe
from frappe.utils import getdate, today, date_diff, now_datetime
import json

from .whatsapp_utils import mark_as_read, send_reply, send_interactive_message
from .user_utils import get_user_by_phone
from .handlers.menu_handlers import handle_menu_trigger, handle_status_filter_trigger
from .handlers.task_handlers import (
    handle_task_selection,
    handle_status_update,
    handle_number_selection,
    handle_more_command,
    handle_load_more_button,
    send_task_list,
    send_my_tasks,
    get_status_emoji
)
from .handlers.creation_handlers import (
    handle_task_creation_trigger,
    handle_pending_task_input,
    handle_my_tasks_trigger,
    handle_menu_add_task,
    handle_guided_flow_input,
    handle_guided_assignee_button,
    handle_guided_deadline_button
)
from .handlers.confirmation_handlers import (
    handle_task_confirmation,
    handle_user_selection,
    handle_change_deadline,
    handle_deadline_number_selection,
    handle_deadline_input,
    handle_deadline_button,
    handle_add_another_task
)


# ============================================
# SCHEDULED TASK: SEND OVERDUE ALERTS
# ============================================

def send_overdue_task_alerts():
    """Send grouped WhatsApp alerts for overdue tasks per user
    
    Called by scheduler at configured times (see hooks.py)
    """
    
    WHATSAPP_ACCOUNT = frappe.conf.get("whatsapp_account")
    if not WHATSAPP_ACCOUNT:
        frappe.log_error("WhatsApp account not configured in site_config.json", "Task Alert Error")
        return
    
    today_date = getdate(today())
    
    # Get all incomplete, overdue tasks from Sprint Board
    overdue_tasks = frappe.get_all(
        "Sprint Board",
        filters={
            "status": ["!=", "Completed"],
            "deadline": ["<", today_date],
            "assigned_to": ["is", "set"]
        },
        fields=["name", "task_name", "deadline", "status", "assigned_to", "last_alerted"]
    )
    
    if not overdue_tasks:
        return
    
    # Group by user
    user_tasks = {}
    
    for task in overdue_tasks:
        # Skip if already alerted today
        if task.last_alerted and getdate(task.last_alerted) == today_date:
            continue
        
        if task.assigned_to not in user_tasks:
            user_tasks[task.assigned_to] = []
        
        days_overdue = date_diff(today_date, getdate(task.deadline))
        user_tasks[task.assigned_to].append({
            "task_name": task.name,
            "task_title": task.task_name,
            "days_overdue": days_overdue,
            "status": task.status
        })
    
    for user, tasks in user_tasks.items():
        if not tasks:
            continue
            
        try:
            mobile_no = frappe.db.get_value("User", user, "mobile_no")
        except Exception as e:
            frappe.log_error(f"Error getting phone for {user}: {str(e)}", "Task Alert Error")
            continue
        
        if not mobile_no:
            frappe.log_error(f"No phone number for user '{user}'", "Task Alert Error")
            continue
        
        mobile_no = str(mobile_no).replace(" ", "").replace("-", "").replace("+", "")
        
        try:
            send_task_list(mobile_no, tasks, WHATSAPP_ACCOUNT, is_initial=True)
            
            # Update last_alerted for all tasks
            for task in tasks:
                frappe.db.set_value("Sprint Board", task["task_name"], "last_alerted", now_datetime())
            
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(
                f"Failed to send grouped alert to '{user}': {str(e)}",
                "Task Alert Error"
            )


# ============================================
# MAIN MESSAGE HANDLER (Entry Point)
# ============================================

def handle_whatsapp_task_response(doc, method=None):
    """Main hook to process incoming WhatsApp messages
    
    This is the entry point called by hooks.py on WhatsApp Message after_insert.
    Routes messages to appropriate handlers based on content and type.
    """
    
    if doc.type != "Incoming":
        return
    
    message = doc.message or ""
    from_number = doc.get("from")
    whatsapp_account = doc.whatsapp_account
    
    # Mark message as read (blue ticks)
    message_id = doc.get("message_id") or doc.get("id")
    mark_as_read(message_id, whatsapp_account)
    
    # Handle text messages
    if doc.content_type == "text":
        _handle_text_message(message, from_number, whatsapp_account)
        return
    
    # Handle button/list replies
    if doc.content_type == "button":
        _handle_button_message(message, from_number, whatsapp_account)
        return


def _handle_text_message(message, from_number, whatsapp_account):
    """Route text messages to appropriate handlers"""
    
    # Check for menu trigger first
    if handle_menu_trigger(message, from_number, whatsapp_account):
        return
    
    # Check for status filter triggers (not started, in progress, on hold)
    if handle_status_filter_trigger(message, from_number, whatsapp_account):
        return
    
    # Check for deadline edit number selection
    if handle_deadline_number_selection(message, from_number, whatsapp_account):
        return
    
    # Check for deadline input (when editing)
    if handle_deadline_input(message, from_number, whatsapp_account):
        return
    
    # Check for "more" command to load more tasks
    if handle_more_command(message, from_number, whatsapp_account):
        return
    
    # Check for number selection (for large lists > 10 items)
    if handle_number_selection(message, from_number, whatsapp_account):
        return
    
    # Check for pending task creation mode (from menu button or guided flow)
    if handle_pending_task_input(message, from_number, whatsapp_account):
        return
    
    # Check for "my tasks" trigger
    if handle_my_tasks_trigger(message, from_number, whatsapp_account):
        return
    
    # Check for task creation triggers
    if handle_task_creation_trigger(message, from_number, whatsapp_account):
        return


def _handle_button_message(message, from_number, whatsapp_account):
    """Route button responses to appropriate handlers"""
    
    # Menu button responses
    if message == "MENU_ADD_TASK":
        handle_menu_add_task(from_number, whatsapp_account)
        return
    
    if message == "MENU_MY_TASKS":
        current_user = get_user_by_phone(from_number)
        if current_user:
            send_my_tasks(from_number, current_user["name"], whatsapp_account)
        else:
            send_reply(from_number, "❌ Your phone number is not linked to any user account.", whatsapp_account)
        return
    
    # Task status update flow
    if message.startswith("SELECT_TASK:"):
        task_id = message.replace("SELECT_TASK:", "").strip()
        handle_task_selection(task_id, from_number, whatsapp_account)
        return
    
    # Load More button for task pagination
    if message == "LOAD_MORE_TASKS":
        handle_load_more_button(from_number, whatsapp_account)
        return
    
    if message.startswith("STATUS:"):
        parts = message.replace("STATUS:", "").split(":", 1)
        if len(parts) == 2:
            status = parts[0]
            task_id = parts[1]
            handle_status_update(task_id, status, from_number, whatsapp_account)
        return
    
    # Task creation confirmation flow
    if message == "CONFIRM_TASKS":
        handle_task_confirmation("CONFIRM_TASKS", from_number, whatsapp_account)
        return
    
    if message == "CANCEL_TASKS":
        handle_task_confirmation("CANCEL_TASKS", from_number, whatsapp_account)
        return
    
    # Change deadline button
    if message == "CHANGE_DEADLINE":
        handle_change_deadline(from_number, whatsapp_account)
        return
    
    # Deadline quick buttons
    if message == "DEADLINE_TODAY":
        handle_deadline_button("TODAY", from_number, whatsapp_account)
        return
    
    if message == "DEADLINE_TOMORROW":
        handle_deadline_button("TOMORROW", from_number, whatsapp_account)
        return
    
    # Add another task button
    if message == "ADD_ANOTHER_TASK":
        handle_add_another_task(from_number, whatsapp_account)
        return
    
    # Guided flow buttons
    if message == "GUIDED_TODAY":
        handle_guided_deadline_button("TODAY", from_number, whatsapp_account)
        return
    
    if message == "GUIDED_TOMORROW":
        handle_guided_deadline_button("TOMORROW", from_number, whatsapp_account)
        return
    
    if message == "GUIDED_ASSIGN_ME":
        handle_guided_assignee_button("ME", from_number, whatsapp_account)
        return
    
    if message.startswith("GUIDED_ASSIGNEE:"):
        user_name = message.replace("GUIDED_ASSIGNEE:", "").strip()
        handle_guided_assignee_button(user_name, from_number, whatsapp_account)
        return
    
    # User selection for ambiguous assignee
    if message.startswith("ASSIGN_USER:"):
        user_name = message.replace("ASSIGN_USER:", "").strip()
        handle_user_selection(user_name, from_number, whatsapp_account)
        return
