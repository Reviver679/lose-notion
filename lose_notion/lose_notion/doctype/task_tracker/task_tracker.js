frappe.ui.form.on('Task Tracker', {
    onload: function(frm) {
        frm.auto_save_timeout = null;
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
