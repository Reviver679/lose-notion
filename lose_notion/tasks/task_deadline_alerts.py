import frappe
from frappe.utils import getdate, today, date_diff, now_datetime

def send_overdue_task_alerts():
    """Send WhatsApp alerts for overdue tasks"""
    
    # WhatsApp Account to use for sending (set this in site_config.json)
    WHATSAPP_ACCOUNT = frappe.conf.get("whatsapp_account")
    if not WHATSAPP_ACCOUNT:
        frappe.log_error("WhatsApp account not configured in site_config.json", "Task Alert Error")
        return  # Stop execution if not configured
    
    try:
        task_tracker = frappe.get_doc("Task Tracker", "Task Tracker")
    except Exception as e:
        frappe.log_error(f"Failed to load Task Tracker: {str(e)}", "Task Alert Error")
        return
    
    today_date = getdate(today())
    task_table = task_tracker.get("task_tracker_table") or []
    
    if not task_table:
        return
    
    for task in task_table:
        # Skip completed tasks
        if task.status == "🟢Completed":
            continue
        
        # Check if task is overdue
        if not task.deadline or getdate(task.deadline) >= today_date:
            continue
        
        # Check if user is assigned
        if not task.assigned_to:
            continue
        
        # Check if already alerted today
        if task.last_alerted and getdate(task.last_alerted) == today_date:
            continue
        
        # Get user's phone number
        try:
            mobile_no = frappe.db.get_value("User", task.assigned_to, "mobile_no")
        except Exception as e:
            frappe.log_error(
                f"Error getting phone for {task.assigned_to}: {str(e)}",
                "Task Alert Error"
            )
            continue
        
        if not mobile_no:
            frappe.log_error(
                f"No phone number for user '{task.assigned_to}' - task '{task.task_name}'",
                "Task Alert Error"
            )
            continue
        
        # Clean phone number
        mobile_no = str(mobile_no).replace(" ", "").replace("-", "").replace("+", "")
        
        # Calculate days overdue
        days_overdue = date_diff(today_date, getdate(task.deadline))
        
        try:
            # Build message
            overdue_text = "1 day" if days_overdue == 1 else f"{days_overdue} days"
            message = (
                f"🚨 *Overdue Task Alert*\n\n"
                f"Task: *{task.task_name}*\n"
                f"Overdue by: {overdue_text}\n\n"
                f"Please update or complete this task."
            )
            
            # Create WhatsApp Message
            wa_msg = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "type": "Outgoing",
                "to": mobile_no,
                "message": message,
                "content_type": "text",
                "whatsapp_account": WHATSAPP_ACCOUNT
            })
            wa_msg.insert(ignore_permissions=True)
            
            # Update last_alerted
            frappe.db.set_value(
                "Task Tracker Table", 
                task.name, 
                "last_alerted", 
                now_datetime()
            )
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(
                f"Failed to send alert for '{task.task_name}': {str(e)}",
                "Task Alert Error"
            )