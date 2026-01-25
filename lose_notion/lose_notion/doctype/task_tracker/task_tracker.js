frappe.ui.form.on('Task Tracker', {
    onload: function(frm) {
        frm.auto_save_timeout = null;
    },
    
    refresh: function(frm) {
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
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __('Completed tasks archived successfully'),
                                        indicator: 'green'
                                    }, 5);
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
            });
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
        
        console.log('Status changed to:', row.status);
        console.log('Current completed_date:', row.completed_date);
        console.log('Row object:', row);
        
        // Auto-set completed date when status is Completed
        if (row.status === 'Completed' || row.status === '🟢Completed') {
            let today = frappe.datetime.get_today();
            console.log('Setting completed_date to:', today);
            
            // Try direct assignment first
            row.completed_date = today;
            
            // Also try using frappe.model.set_value
            frappe.model.set_value(cdt, cdn, 'completed_date', today);
            
            console.log('After setting - completed_date:', row.completed_date);
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
            frappe.model.set_value(cdt, cdn, 'status', 'Not Started');
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