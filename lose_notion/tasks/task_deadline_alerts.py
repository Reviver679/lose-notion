import frappe
from frappe.utils import getdate, today, date_diff, now_datetime
import json

# ============================================
# PART 1: SEND GROUPED OVERDUE TASK ALERTS
# ============================================

def send_overdue_task_alerts():
    """Send grouped WhatsApp alerts for overdue tasks per user"""
    
    WHATSAPP_ACCOUNT = frappe.conf.get("whatsapp_account")
    if not WHATSAPP_ACCOUNT:
        frappe.log_error("WhatsApp account not configured in site_config.json", "Task Alert Error")
        return
    
    try:
        task_tracker = frappe.get_doc("Task Tracker", "Task Tracker")
    except Exception as e:
        frappe.log_error(f"Failed to load Task Tracker: {str(e)}", "Task Alert Error")
        return
    
    today_date = getdate(today())
    task_table = task_tracker.get("task_tracker_table") or []
    
    if not task_table:
        return
    
    # Group overdue tasks by user
    user_tasks = {}
    
    for task in task_table:
        if task.status == "🟢Completed":
            continue
        
        if not task.deadline or getdate(task.deadline) >= today_date:
            continue
        
        if not task.assigned_to:
            continue
        
        if task.last_alerted and getdate(task.last_alerted) == today_date:
            continue
        
        if task.assigned_to not in user_tasks:
            user_tasks[task.assigned_to] = []
        
        days_overdue = date_diff(today_date, getdate(task.deadline))
        user_tasks[task.assigned_to].append({
            "task_name": task.name,
            "task_title": task.task_name,
            "days_overdue": days_overdue,
            "status": task.status  # Include status for emoji display
        })
    
    for user, tasks in user_tasks.items():
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
            
            for task in tasks:
                frappe.db.set_value(
                    "Task Tracker Table", 
                    task["task_name"], 
                    "last_alerted", 
                    now_datetime()
                )
            
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(
                f"Failed to send grouped alert to '{user}': {str(e)}",
                "Task Alert Error"
            )


def get_status_emoji(status):
    """Extract just the emoji from status"""
    status_emojis = {
        "⚫Not Started": "⚫",
        "🔵In Progress": "🔵",  # CORRECT: Blue, not yellow
        "🟢Completed": "🟢",
        "🟠On Hold": "🟠"
    }
    return status_emojis.get(status, "⚫")


def send_task_list(to_number, tasks, whatsapp_account, is_initial=False):
    """Send the task list as an interactive message"""
    
    if not tasks:
        send_reply(to_number, "✅ All tasks are completed! Great job! 🎉", whatsapp_account)
        return
    
    buttons = []
    task_list_text = ""
    
    for idx, task in enumerate(tasks, 1):
        if isinstance(task, dict):
            task_name = task["task_name"]
            task_title = task["task_title"]
            days_overdue = task["days_overdue"]
            status = task.get("status", "⚫Not Started")
        else:
            # If task is a row object
            task_name = task.name
            task_title = task.task_name
            days_overdue = date_diff(getdate(today()), getdate(task.deadline))
            status = task.status
        
        status_emoji = get_status_emoji(status)
        overdue_text = "1 day" if days_overdue == 1 else f"{days_overdue} days"
        
        # Show status emoji at the end of each task line
        task_list_text += f"{idx}. {task_title} ({overdue_text} overdue) {status_emoji}\n"
        
        buttons.append({
            "id": f"SELECT_TASK:{task_name}",
            "title": task_title[:20],
            "description": f"Overdue by {overdue_text}"[:72]
        })
    
    total_tasks = len(tasks)
    
    if is_initial:
        header = f"🚨 *You have {total_tasks} overdue task{'s' if total_tasks > 1 else ''}*"
    else:
        header = f"📋 *{total_tasks} remaining task{'s' if total_tasks > 1 else ''}*"
    
    message_body = (
        f"{header}\n\n"
        f"{task_list_text}\n"
        f"Select a task to update its status."
    )
    
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


# ============================================
# PART 2: HANDLE WHATSAPP RESPONSES
# ============================================

def handle_whatsapp_task_response(doc, method=None):
    """Hook to process incoming WhatsApp messages for task management."""
    
    if doc.type != "Incoming":
        return
    
    if doc.content_type != "button":
        return
    
    message = doc.message or ""
    from_number = doc.get("from")
    whatsapp_account = doc.whatsapp_account
    
    if message.startswith("SELECT_TASK:"):
        task_row_name = message.replace("SELECT_TASK:", "").strip()
        handle_task_selection(task_row_name, from_number, whatsapp_account)
        return
    
    if message.startswith("STATUS:"):
        parts = message.replace("STATUS:", "").split(":", 1)
        if len(parts) == 2:
            status = parts[0]
            task_row_name = parts[1]
            handle_status_update(task_row_name, status, from_number, whatsapp_account)
        return


def handle_task_selection(task_row_name, from_number, whatsapp_account):
    """When user selects a task, show status options (excluding current status)"""
    
    try:
        task_data = frappe.db.get_value(
            "Task Tracker Table",
            task_row_name,
            ["task_name", "status"],
            as_dict=True
        )
        
        if not task_data:
            send_reply(from_number, "❌ Task not found.", whatsapp_account)
            return
        
        current_status = task_data.status
        
        # All possible status options - CORRECT EMOJIS
        all_statuses = [
            {"id": f"STATUS:🟢Completed:{task_row_name}", "title": "Completed 🟢", "status": "🟢Completed"},
            {"id": f"STATUS:🔵In Progress:{task_row_name}", "title": "In Progress 🔵", "status": "🔵In Progress"},
            {"id": f"STATUS:🟠On Hold:{task_row_name}", "title": "On Hold 🟠", "status": "🟠On Hold"},
            {"id": f"STATUS:⚫Not Started:{task_row_name}", "title": "Not Started ⚫", "status": "⚫Not Started"}
        ]
        
        # Filter out the current status
        status_buttons = [
            {"id": s["id"], "title": s["title"]} 
            for s in all_statuses 
            if s["status"] != current_status
        ][:3]  # Max 3 buttons for WhatsApp
        
        message_body = (
            f"📋 *Task:* {task_data.task_name}\n"
            f"📌 *Current Status:* {current_status}\n\n"
            f"Select new status:"
        )
        
        wa_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": from_number,
            "message": message_body,
            "content_type": "interactive",
            "buttons": json.dumps(status_buttons),
            "whatsapp_account": whatsapp_account
        })
        wa_msg.insert(ignore_permissions=True)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Error handling task selection: {str(e)}", "Task Alert Error")
        send_reply(from_number, "❌ An error occurred. Please try again.", whatsapp_account)


def handle_status_update(task_row_name, new_status, from_number, whatsapp_account):
    """Update the task status based on user selection"""
    
    try:
        task_data = frappe.db.get_value(
            "Task Tracker Table",
            task_row_name,
            ["task_name", "status", "parent", "assigned_to"],
            as_dict=True
        )
        
        if not task_data:
            send_reply(from_number, "❌ Task not found.", whatsapp_account)
            return
        
        # Update the task status
        frappe.db.set_value(
            "Task Tracker Table",
            task_row_name,
            "status",
            new_status
        )
        frappe.db.commit()
        
        status_emoji = get_status_emoji(new_status)
        
        # Status display mapping - CORRECT EMOJIS
        status_display = {
            "🟢Completed": "Completed 🟢",
            "🔵In Progress": "In Progress 🔵",  # CORRECT: Blue
            "🟠On Hold": "On Hold 🟠",
            "⚫Not Started": "Not Started ⚫"
        }
        
        display_status = status_display.get(new_status, new_status)
        
        send_reply(
            from_number,
            f"✅ *{task_data.task_name}*\n\nStatus updated to {display_status}",
            whatsapp_account
        )
        
        send_remaining_tasks(from_number, task_data.assigned_to, whatsapp_account)
        
    except Exception as e:
        frappe.log_error(f"Error updating task status: {str(e)}", "Task Completion Error")
        send_reply(from_number, "❌ An error occurred. Please try again.", whatsapp_account)



def send_remaining_tasks(to_number, assigned_to, whatsapp_account):
    """Send the remaining overdue tasks after a status update"""
    
    try:
        task_tracker = frappe.get_doc("Task Tracker", "Task Tracker")
        today_date = getdate(today())
        task_table = task_tracker.get("task_tracker_table") or []
        
        remaining_tasks = []
        
        for task in task_table:
            if task.status == "🟢Completed":
                continue
            
            if task.assigned_to != assigned_to:
                continue
            
            if not task.deadline or getdate(task.deadline) >= today_date:
                continue
            
            days_overdue = date_diff(today_date, getdate(task.deadline))
            remaining_tasks.append({
                "task_name": task.name,
                "task_title": task.task_name,
                "days_overdue": days_overdue,
                "status": task.status
            })
        
        if remaining_tasks:
            send_task_list(to_number, remaining_tasks, whatsapp_account, is_initial=False)
        else:
            send_reply(
                to_number, 
                "🎉 *All overdue tasks completed!*\n\nYou're all caught up!", 
                whatsapp_account
            )
            
    except Exception as e:
        frappe.log_error(f"Error sending remaining tasks: {str(e)}", "Task Alert Error")


def send_reply(to_number, message, whatsapp_account):
    """Send a text reply message"""
    try:
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