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

# Special filter triggers (not actual status values)
SPECIAL_FILTER_TRIGGERS = ['today', 'overdue']

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
        "• `not started` / `in progress` / `on hold` - Filter by status\n"
        "• `today` - Tasks due today\n"
        "• `overdue` - Overdue tasks"
    )
    
    send_interactive_message(from_number, message_body, buttons, whatsapp_account)
    return True


def handle_status_filter_trigger(message, from_number, whatsapp_account):
    """Handle status filter triggers like 'not started', 'in progress', 'on hold', 'today', 'overdue'"""
    message_lower = message.strip().lower()
    
    current_user = get_user_by_phone(from_number)
    if not current_user:
        # Only return True if it's a valid trigger
        if message_lower in STATUS_FILTER_TRIGGERS or message_lower in SPECIAL_FILTER_TRIGGERS:
            send_reply(
                from_number,
                "❌ Your phone number is not linked to any user account.",
                whatsapp_account
            )
            return True
        return False
    
    # Handle status filter triggers
    if message_lower in STATUS_FILTER_TRIGGERS:
        status = STATUS_FILTER_TRIGGERS[message_lower]
        send_filtered_tasks(from_number, current_user["name"], status, whatsapp_account)
        return True
    
    # Handle special filter triggers
    if message_lower == 'today':
        send_today_tasks(from_number, current_user["name"], whatsapp_account)
        return True
    
    if message_lower == 'overdue':
        send_overdue_tasks(from_number, current_user["name"], whatsapp_account)
        return True
    
    return False


def send_filtered_tasks(to_number, assigned_to, status, whatsapp_account):
    """Send tasks filtered by status with status counts"""
    from frappe.utils import getdate, today
    
    send_typing_indicator(to_number, whatsapp_account)
    
    try:
        today_date = getdate(today())
        
        # Get all incomplete tasks to compute status counts
        all_tasks = frappe.get_all(
            "Sprint Board",
            filters={
                "status": ["!=", "Completed"],
                "assigned_to": assigned_to
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        # Filter tasks and compute status counts
        task_list = []
        status_counts = {
            "not_started": 0,
            "in_progress": 0,
            "overdue": 0,
            "on_hold": 0
        }
        
        for task in all_tasks:
            # Check if task is overdue
            is_overdue = task.deadline and getdate(task.deadline) < today_date
            
            # Count all statuses
            if task.status == "On Hold":
                status_counts["on_hold"] += 1
            elif is_overdue:
                status_counts["overdue"] += 1
            elif task.status == "Not Started":
                status_counts["not_started"] += 1
            elif task.status == "In Progress":
                status_counts["in_progress"] += 1
            
            # Only add to task list if matches filter
            if task.status == status:
                days_text = get_days_text(task.deadline, today_date)
                task_list.append({
                    "task_id": task.name,
                    "task_title": task.task_name,
                    "days_text": days_text,
                    "status": task.status,
                    "deadline": task.deadline
                })
        
        if not task_list:
            send_reply(
                to_number,
                f"✅ No tasks with status *{get_status_display(status)}*",
                whatsapp_account
            )
            return
        
        # Sort by deadline
        def sort_key(t):
            if not t["deadline"]:
                return "9999-99-99"
            return str(getdate(t["deadline"]))
        
        task_list.sort(key=sort_key)
        
        # Determine exclude_status for summary
        exclude_map = {
            "Not Started": "not_started",
            "In Progress": "in_progress",
            "On Hold": "on_hold"
        }
        exclude_status = exclude_map.get(status)
        
        send_task_list_with_numbers(
            to_number, task_list, whatsapp_account, 
            f"Tasks - {get_status_display(status)}", 
            status_counts=status_counts,
            exclude_status=exclude_status
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending filtered tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)


def send_today_tasks(to_number, assigned_to, whatsapp_account):
    """Send tasks due today with status counts"""
    from frappe.utils import getdate, today
    
    send_typing_indicator(to_number, whatsapp_account)
    
    try:
        today_date = getdate(today())
        
        # Get all incomplete tasks to compute status counts
        all_tasks = frappe.get_all(
            "Sprint Board",
            filters={
                "status": ["!=", "Completed"],
                "assigned_to": assigned_to
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        # Filter tasks due today and compute status counts
        task_list = []
        status_counts = {
            "not_started": 0,
            "in_progress": 0,
            "overdue": 0,
            "on_hold": 0
        }
        
        for task in all_tasks:
            # Check if task is overdue or due today
            is_today = task.deadline and getdate(task.deadline) == today_date
            is_overdue = task.deadline and getdate(task.deadline) < today_date
            
            # Count all statuses
            if task.status == "On Hold":
                status_counts["on_hold"] += 1
            elif is_overdue:
                status_counts["overdue"] += 1
            elif task.status == "Not Started":
                status_counts["not_started"] += 1
            elif task.status == "In Progress":
                status_counts["in_progress"] += 1
            
            # Only add to task list if due today (and not On Hold)
            if is_today and task.status != "On Hold":
                days_text = get_days_text(task.deadline, today_date)
                task_list.append({
                    "task_id": task.name,
                    "task_title": task.task_name,
                    "days_text": days_text,
                    "status": task.status,
                    "deadline": task.deadline
                })
        
        if not task_list:
            send_reply(
                to_number,
                "✅ No tasks due today!",
                whatsapp_account
            )
            return
        
        # Sort by status (In Progress first, then Not Started)
        def sort_key(t):
            status_order = {"In Progress": 0, "Not Started": 1}
            return status_order.get(t["status"], 2)
        
        task_list.sort(key=sort_key)
        
        send_task_list_with_numbers(
            to_number, task_list, whatsapp_account, 
            "📅 Tasks Due Today", 
            status_counts=status_counts
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending today tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)


def send_overdue_tasks(to_number, assigned_to, whatsapp_account):
    """Send overdue tasks (deadline < today, not Completed or On Hold) with status counts"""
    from frappe.utils import getdate, today, date_diff
    
    send_typing_indicator(to_number, whatsapp_account)
    
    try:
        today_date = getdate(today())
        
        # Get all incomplete tasks (excluding On Hold for overdue filter)
        all_tasks = frappe.get_all(
            "Sprint Board",
            filters={
                "status": ["!=", "Completed"],
                "assigned_to": assigned_to
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        # Filter overdue tasks and compute status counts
        task_list = []
        status_counts = {
            "not_started": 0,
            "in_progress": 0,
            "overdue": 0,
            "on_hold": 0
        }
        
        for task in all_tasks:
            # Check if task is overdue
            is_overdue = task.deadline and getdate(task.deadline) < today_date
            
            # Count all statuses
            if task.status == "On Hold":
                status_counts["on_hold"] += 1
            elif is_overdue:
                status_counts["overdue"] += 1
            elif task.status == "Not Started":
                status_counts["not_started"] += 1
            elif task.status == "In Progress":
                status_counts["in_progress"] += 1
            
            # Only add to task list if overdue and not On Hold
            if is_overdue and task.status != "On Hold":
                days_overdue = date_diff(today_date, getdate(task.deadline))
                days_text = f"{days_overdue} day{'s' if days_overdue > 1 else ''} overdue"
                task_list.append({
                    "task_id": task.name,
                    "task_title": task.task_name,
                    "days_text": days_text,
                    "status": task.status,
                    "deadline": task.deadline
                })
        
        if not task_list:
            send_reply(
                to_number,
                "✅ No overdue tasks! Great job staying on track! 🎉",
                whatsapp_account
            )
            return
        
        # Sort by most overdue first
        def sort_key(t):
            if not t["deadline"]:
                return "0000-00-00"
            return str(getdate(t["deadline"]))
        
        task_list.sort(key=sort_key)
        
        send_task_list_with_numbers(
            to_number, task_list, whatsapp_account, 
            "🔴 Overdue Tasks", 
            status_counts=status_counts,
            exclude_status="overdue"
        )
        
    except Exception as e:
        frappe.log_error(f"Error sending overdue tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)

