# Copyright (c) 2026, alfaEdge and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, nowdate, now_datetime, getdate

class TaskTracker(Document):
    pass

@frappe.whitelist()
def archive_completed_tasks():
    """Move completed tasks older than 1 day to Task History"""
    
    one_day_ago = getdate(add_days(nowdate(), -1))
    today = getdate(nowdate())
    
    # Get the single Task Tracker document
    doc = frappe.get_doc('Task Tracker', 'Task Tracker')
    
    archived_count = 0
    total_tasks = 0
    completed_tasks = 0
    archived_tasks_info = []
    tasks_to_remove = []
    
    # Loop through child table
    for task in doc.task_tracker_table:
        total_tasks += 1
        
        # Check if task is completed and older than 1 day
        is_completed = task.status in ['Completed', '🟢Completed'] or 'Completed' in str(task.status)
        
        if is_completed:
            completed_tasks += 1
            
            if task.completed_date:
                # Convert completed_date to date object for comparison
                completed_date = getdate(task.completed_date)
                
                # ONLY archive if completed date is older than 1 day
                if completed_date <= one_day_ago:
                    # Add to archived tasks info - ONLY HERE
                    task_info = f"<strong>{task.task_name}</strong> - Completed on {task.completed_date}"
                    archived_tasks_info.append(task_info)
                    
                    # Create Task History record
                    history = frappe.get_doc({
                        'doctype': 'Task History',
                        'task_name': task.task_name,
                        'assigned_to': task.assigned_to,
                        'status': task.status,
                        'deadline': task.deadline,
                        'completed_date': task.completed_date,
                        'original_tracker': 'Task Tracker',
                        'archived_on': now_datetime()
                    })
                    history.insert(ignore_permissions=True)
                    
                    # Mark for removal
                    tasks_to_remove.append(task)
                    archived_count += 1
    
    # Remove archived tasks from the child table
    for task in tasks_to_remove:
        doc.remove(task)
    
    # Save the document if any tasks were removed
    if tasks_to_remove:
        doc.save(ignore_permissions=True)
    
    frappe.db.commit()
    
    # Return detailed info
    return {
        'status': 'success',
        'archived_count': archived_count,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'today': str(today),
        'cutoff': str(one_day_ago),
        'archived_tasks': archived_tasks_info
    }