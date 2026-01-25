# Copyright (c) 2026, alfaEdge and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import add_days, nowdate, now_datetime


class TaskTracker(Document):
	pass


@frappe.whitelist()
def archive_completed_tasks():
	"""Move completed tasks older than 1 day to Task History"""
	try:
		one_day_ago = add_days(nowdate(), -1)
		
		# Find all Task Tracker documents
		task_trackers = frappe.get_all('Task Tracker', fields=['name'])
		
		archived_count = 0
		
		for tracker in task_trackers:
			# Get the Task Tracker document
			doc = frappe.get_doc('Task Tracker', tracker.name)
			
			tasks_to_remove = []
			
			# Loop through child table
			for task in doc.task_tracker_table:
				# Check if task is completed and older than 1 day
				if task.status == 'Completed' and task.completed_date and task.completed_date <= one_day_ago:
					
					# Create Task History record
					history = frappe.get_doc({
						'doctype': 'Task History',
						'task_name': task.task_name,
						'assigned_to': task.assigned_to,
						'status': task.status,
						'deadline': task.deadline,
						'completed_date': task.completed_date,
						'original_tracker': tracker.name,
						'archived_on': now_datetime()
					})
					history.insert(ignore_permissions=True)
					
					# Mark for removal
					tasks_to_remove.append(task)
					archived_count += 1
			
			# Remove archived tasks from the child table
			for task in tasks_to_remove:
				doc.remove(task)
			
			# Save the parent document if any tasks were removed
			if tasks_to_remove:
				doc.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		frappe.msgprint(
			_('Successfully archived {0} completed task(s)').format(archived_count),
			indicator='green',
			alert=True
		)
		
		return {
			'status': 'success',
			'archived_count': archived_count
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), 'Archive Completed Tasks Error')
		frappe.throw(_('Error archiving tasks: {0}').format(str(e)))