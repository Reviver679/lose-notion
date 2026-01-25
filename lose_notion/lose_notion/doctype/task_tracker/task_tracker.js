frappe.ui.form.on('Task Tracker', {
    onload: function(frm) {
        frm.auto_save_timeout = null;
    },
    
    refresh: function(frm) {
        // Add "Add Multiple Tasks" button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Add Multiple Tasks'), function() {
                let tasks_added = [];
                
                function show_add_task_dialog() {
                    let d = new frappe.ui.Dialog({
                        title: __('Add Multiple Tasks'),
                        fields: [
                            {
                                label: __('Task Name'),
                                fieldname: 'task_name',
                                fieldtype: 'Data',
                                reqd: 1,
                                description: tasks_added.length > 0 
                                    ? `<strong style="color: green;">✓ ${tasks_added.length} task(s) added</strong>` 
                                    : ''
                            }
                        ],
                        primary_action_label: __('Add & Next'),
                        primary_action: function(values) {
                            if (values.task_name && values.task_name.trim()) {
                                // Add the task to the child table
                                let row = frm.add_child('task_tracker_table', {
                                    task_name: values.task_name.trim(),
                                    status: '⚫Not Started'
                                });
                                tasks_added.push(values.task_name.trim());
                                
                                frappe.show_alert({
                                    message: __('Task added: ') + values.task_name.trim(),
                                    indicator: 'green'
                                }, 2);
                                
                                // Clear the field and show dialog again
                                d.hide();
                                show_add_task_dialog();
                            }
                        },
                        secondary_action_label: __('Done'),
                        secondary_action: function() {
                            d.hide();
                            if (tasks_added.length > 0) {
                                frm.refresh_field('task_tracker_table');
                                
                                // Auto-save after adding tasks
                                if (frm.is_dirty()) {
                                    frm.save().then(() => {
                                        frappe.show_alert({
                                            message: __(`${tasks_added.length} task(s) added and saved!`),
                                            indicator: 'green'
                                        }, 3);
                                    });
                                }
                            }
                        }
                    });
                    
                    d.show();
                    
                    // Focus on the input field
                    setTimeout(() => {
                        d.fields_dict.task_name.$input.focus();
                    }, 100);
                    
                    // Allow Enter key to add task
                    d.fields_dict.task_name.$input.on('keypress', function(e) {
                        if (e.which === 13) { // Enter key
                            e.preventDefault();
                            d.primary_action();
                        }
                    });
                }
                
                show_add_task_dialog();
            }, __('Actions'));
        }
        
        // Add "Archive Completed Tasks" button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Archive Completed Tasks'), function() {
                frappe.confirm(
                    __('This will move all completed tasks (older than 1 day) to Task History. Continue?'),
                    function() {
                        // User confirmed
                        frappe.call({
                            method: 'lose_notion.lose_notion.doctype.task_tracker.task_tracker.archive_completed_tasks',
                            args: {},
                            freeze: true,
                            freeze_message: __('Archiving completed tasks...'),
                            callback: function(r) {
                                if (!r.exc && r.message) {
                                    let data = r.message;
                                    
                                    // Build summary message without detailed list
                                    let message = `
                                        <div style="font-family: Arial, sans-serif;">
                                            <h4 style="margin-bottom: 15px; color: #2c3e50;">📊 Archive Summary</h4>
                                            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                                                <tr style="background-color: #f8f9fa;">
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Today's Date:</strong></td>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.today}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Cutoff Date:</strong></td>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.cutoff}</td>
                                                </tr>
                                                <tr style="background-color: #f8f9fa;">
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Total Tasks:</strong></td>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.total_tasks}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Completed Tasks:</strong></td>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.completed_tasks}</td>
                                                </tr>
                                                <tr style="background-color: #d4edda;">
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>✅ Archived Tasks:</strong></td>
                                                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>${data.archived_count}</strong></td>
                                                </tr>
                                            </table>
                                        </div>
                                    `;
                                    
                                    frappe.msgprint({
                                        title: __('Archive Results'),
                                        indicator: 'green',
                                        message: message
                                    });
                                    
                                    frm.reload_doc();
                                } else {
                                    frappe.show_alert({
                                        message: __('Error archiving tasks'),
                                        indicator: 'red'
                                    }, 5);
                                }
                            },
                            error: function(r) {
                                frappe.show_alert({
                                    message: __('Failed to archive tasks'),
                                    indicator: 'red'
                                }, 5);
                            }
                        });
                    }
                );
            }, __('Actions'));
        }
    },
    
    validate: function(frm) {
        // Remove rows with blank task names before saving
        let rows_to_remove = [];
        
        frm.doc.task_tracker_table.forEach(function(row) {
            if (!row.task_name || row.task_name.trim() === '') {
                rows_to_remove.push(row);
            }
        });
        
        if (rows_to_remove.length > 0) {
            // Show warning message
            frappe.show_alert({
                message: __('Please enter a task name'),
                indicator: 'orange'
            }, 3);
            
            // Remove blank rows
            rows_to_remove.forEach(function(row) {
                let index = frm.doc.task_tracker_table.indexOf(row);
                if (index > -1) {
                    frm.doc.task_tracker_table.splice(index, 1);
                }
            });
            
            frm.refresh_field('task_tracker_table');
        }
    }
});

frappe.ui.form.on('Task Tracker Table', {
    task_name: function(frm, cdt, cdn) {
        trigger_auto_save(frm);
    },
    
    assigned_to: function(frm, cdt, cdn) {
        trigger_auto_save(frm);
    },
    
    status: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Auto-set completed date when status is Completed
        if (row.status === 'Completed' || row.status === '🟢Completed') {
            let today = frappe.datetime.get_today();
            row.completed_date = today;
            frappe.model.set_value(cdt, cdn, 'completed_date', today);
        } else {
            // Clear completed_date if status is changed from Completed to something else
            frappe.model.set_value(cdt, cdn, 'completed_date', null);
        }
        
        trigger_auto_save(frm);
    },
    
    deadline: function(frm, cdt, cdn) {
        trigger_auto_save(frm);
    },
    
    task_tracker_table_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.status) {
            frappe.model.set_value(cdt, cdn, 'status', '⚫Not Started');
        }
    }
});

function trigger_auto_save(frm) {
    if (frm.auto_save_timeout) {
        clearTimeout(frm.auto_save_timeout);
    }
    
    frm.auto_save_timeout = setTimeout(() => {
        if (frm.is_dirty()) {
            frm.save('Save', null, null, () => {
                frappe.show_alert({
                    message: __('Tasks auto-saved'),
                    indicator: 'green'
                }, 2);
            });
        }
    }, 800);
}