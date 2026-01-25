frappe.ui.form.on('Task Tracker', {
    onload: function(frm) {
        frm.auto_save_timeout = null;
        frm.active_filters = {}; // Store active filters
        frm.original_rows = null; // Store original rows for reset
    },
    
    refresh: function(frm) {
        // Add standalone "Filter Tasks" button (outside Actions)
        if (!frm.is_new()) {
            // Store original rows if not already stored
            if (!frm.original_rows && frm.doc.task_tracker_table) {
                frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
            }
            
            // Get unique values for dropdowns
            let rows = frm.original_rows || frm.doc.task_tracker_table || [];
            
            let assigned_options = [''].concat([...new Set(rows.map(r => r.assigned_to).filter(Boolean))]);
            let status_options = ['', '⚫Not Started', '🔵In Progress', '🟢Completed', '🟠On Hold'];
            
            // Count active filters
            let filter_count = Object.values(frm.active_filters || {}).filter(v => v).length;
            let filter_btn_label = filter_count > 0 ? __(`🔍 Filter (${filter_count})`) : __('🔍 Filter');
            
            frm.add_custom_button(filter_btn_label, function() {
                let d = new frappe.ui.Dialog({
                    title: __('Filter Tasks'),
                    fields: [
                        {
                            label: __('Task Name'),
                            fieldname: 'task_name',
                            fieldtype: 'Data',
                            description: __('Contains text (case-insensitive)'),
                            default: frm.active_filters?.task_name || ''
                        },
                        {
                            fieldtype: 'Column Break'
                        },
                        {
                            label: __('Assigned To'),
                            fieldname: 'assigned_to',
                            fieldtype: 'Select',
                            options: assigned_options,
                            default: frm.active_filters?.assigned_to || ''
                        },
                        {
                            fieldtype: 'Section Break'
                        },
                        {
                            label: __('Status'),
                            fieldname: 'status',
                            fieldtype: 'Select',
                            options: status_options,
                            default: frm.active_filters?.status || ''
                        },
                        {
                            fieldtype: 'Column Break'
                        },
                        {
                            label: __('Show Completed'),
                            fieldname: 'hide_completed',
                            fieldtype: 'Select',
                            options: [
                                { label: 'Show All', value: '' },
                                { label: 'Hide Completed', value: 'hide' },
                                { label: 'Only Completed', value: 'only' }
                            ],
                            default: frm.active_filters?.hide_completed || ''
                        },
                        {
                            fieldtype: 'Section Break',
                            label: __('Date Filters')
                        },
                        {
                            label: __('Deadline From'),
                            fieldname: 'deadline_from',
                            fieldtype: 'Date',
                            default: frm.active_filters?.deadline_from || ''
                        },
                        {
                            fieldtype: 'Column Break'
                        },
                        {
                            label: __('Deadline To'),
                            fieldname: 'deadline_to',
                            fieldtype: 'Date',
                            default: frm.active_filters?.deadline_to || ''
                        },
                        {
                            fieldtype: 'Section Break'
                        },
                        {
                            label: __('Completed Date From'),
                            fieldname: 'completed_from',
                            fieldtype: 'Date',
                            default: frm.active_filters?.completed_from || ''
                        },
                        {
                            fieldtype: 'Column Break'
                        },
                        {
                            label: __('Completed Date To'),
                            fieldname: 'completed_to',
                            fieldtype: 'Date',
                            default: frm.active_filters?.completed_to || ''
                        }
                    ],
                    primary_action_label: __('Apply Filters'),
                    primary_action: function(values) {
                        // Store filter values
                        frm.active_filters = values;
                        
                        // Get original rows
                        let all_rows = frm.original_rows || [];
                        
                        // Apply filters
                        let filtered_rows = all_rows.filter(row => {
                            // Task Name filter (contains, case-insensitive)
                            if (values.task_name) {
                                if (!row.task_name || !row.task_name.toLowerCase().includes(values.task_name.toLowerCase())) {
                                    return false;
                                }
                            }
                            
                            // Assigned To filter
                            if (values.assigned_to) {
                                if (row.assigned_to !== values.assigned_to) {
                                    return false;
                                }
                            }
                            
                            // Status filter
                            if (values.status) {
                                if (row.status !== values.status) {
                                    return false;
                                }
                            }
                            
                            // Hide/Show Completed filter
                            if (values.hide_completed === 'hide') {
                                if (row.status === '🟢Completed') {
                                    return false;
                                }
                            } else if (values.hide_completed === 'only') {
                                if (row.status !== '🟢Completed') {
                                    return false;
                                }
                            }
                            
                            // Deadline From filter
                            if (values.deadline_from) {
                                if (!row.deadline || row.deadline < values.deadline_from) {
                                    return false;
                                }
                            }
                            
                            // Deadline To filter
                            if (values.deadline_to) {
                                if (!row.deadline || row.deadline > values.deadline_to) {
                                    return false;
                                }
                            }
                            
                            // Completed Date From filter
                            if (values.completed_from) {
                                if (!row.completed_date || row.completed_date < values.completed_from) {
                                    return false;
                                }
                            }
                            
                            // Completed Date To filter
                            if (values.completed_to) {
                                if (!row.completed_date || row.completed_date > values.completed_to) {
                                    return false;
                                }
                            }
                            
                            return true;
                        });
                        
                        // Update the table with filtered rows
                        frm.doc.task_tracker_table = filtered_rows;
                        frm.refresh_field('task_tracker_table');
                        
                        d.hide();
                        
                        let active_filter_count = Object.values(values).filter(v => v).length;
                        frappe.show_alert({
                            message: __(`Showing ${filtered_rows.length} of ${all_rows.length} tasks (${active_filter_count} filter(s) active)`),
                            indicator: 'blue'
                        }, 4);
                        
                        // Refresh to update button label
                        frm.refresh();
                    },
                    secondary_action_label: __('Clear Filters'),
                    secondary_action: function() {
                        // Reset filters
                        frm.active_filters = {};
                        
                        // Restore original rows
                        if (frm.original_rows) {
                            frm.doc.task_tracker_table = JSON.parse(JSON.stringify(frm.original_rows));
                            frm.refresh_field('task_tracker_table');
                        }
                        
                        d.hide();
                        
                        frappe.show_alert({
                            message: __('Filters cleared - showing all tasks'),
                            indicator: 'green'
                        }, 3);
                        
                        // Refresh to update button label
                        frm.refresh();
                    }
                });
                
                d.show();
            });
            
            // Add "X" Clear Filter button if filters are active
            if (filter_count > 0) {
                frm.add_custom_button(__('✕'), function() {
                    // Reset filters
                    frm.active_filters = {};
                    
                    // Restore original rows
                    if (frm.original_rows) {
                        frm.doc.task_tracker_table = JSON.parse(JSON.stringify(frm.original_rows));
                        frm.refresh_field('task_tracker_table');
                    }
                    
                    frappe.show_alert({
                        message: __('Filters cleared - showing all tasks'),
                        indicator: 'green'
                    }, 3);
                    
                    // Refresh to update buttons
                    frm.refresh();
                });
                
                // Style the X button to look like a clear filter button
                setTimeout(() => {
                    frm.$wrapper.find('.btn-secondary:contains("✕")').css({
                        'padding': '5px 10px',
                        'margin-left': '-8px',
                        'border-left': 'none',
                        'background-color': '#f8d7da',
                        'border-color': '#f5c6cb',
                        'color': '#721c24'
                    }).hover(
                        function() { $(this).css({'background-color': '#f1b0b7', 'color': '#491217'}); },
                        function() { $(this).css({'background-color': '#f8d7da', 'color': '#721c24'}); }
                    );
                }, 100);
            }
        }
        
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
                                
                                // Also add to original_rows to keep sync
                                if (frm.original_rows) {
                                    frm.original_rows.push({
                                        task_name: values.task_name.trim(),
                                        status: '⚫Not Started',
                                        name: row.name // Store the name for syncing
                                    });
                                }
                                
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
                                        
                                        // Update original_rows after save
                                        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
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
        // Restore original rows before saving to ensure all data is saved
        if (frm.original_rows && frm.original_rows.length > 0) {
            // Check if we're in filtered mode by comparing with current displayed rows
            let current_names = new Set(frm.doc.task_tracker_table.map(r => r.name));
            let original_names = new Set(frm.original_rows.map(r => r.name));
            
            // If we have filters active (some original rows not in current view)
            let has_hidden_rows = [...original_names].some(name => !current_names.has(name));
            
            if (has_hidden_rows) {
                // Merge: keep updates from current rows, add back hidden rows
                let merged_rows = [];
                
                // First, add rows that are currently visible (with their updates)
                frm.doc.task_tracker_table.forEach(row => {
                    merged_rows.push(row);
                });
                
                // Then add back rows that were hidden by filter
                frm.original_rows.forEach(orig_row => {
                    if (!current_names.has(orig_row.name)) {
                        merged_rows.push(orig_row);
                    }
                });
                
                frm.doc.task_tracker_table = merged_rows;
            }
        }
        
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
        
        // Update original_rows after validation
        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
    },
    
    after_save: function(frm) {
        // Update original_rows after save
        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
        frm.active_filters = {};
    }
});

frappe.ui.form.on('Task Tracker Table', {
    task_name: function(frm, cdt, cdn) {
        sync_row_to_original(frm, cdt, cdn);
        trigger_auto_save(frm);
    },
    
    assigned_to: function(frm, cdt, cdn) {
        sync_row_to_original(frm, cdt, cdn);
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
        
        sync_row_to_original(frm, cdt, cdn);
        trigger_auto_save(frm);
    },
    
    deadline: function(frm, cdt, cdn) {
        sync_row_to_original(frm, cdt, cdn);
        trigger_auto_save(frm);
    },
    
    task_tracker_table_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.status) {
            frappe.model.set_value(cdt, cdn, 'status', '⚫Not Started');
        }
    },
    
    before_task_tracker_table_remove: function(frm, cdt, cdn) {
        // Remove from original_rows BEFORE the row is removed from the table
        if (frm.original_rows) {
            let idx = frm.original_rows.findIndex(r => r.name === cdn);
            if (idx > -1) {
                frm.original_rows.splice(idx, 1);
            }
        }
    }
});

function sync_row_to_original(frm, cdt, cdn) {
    // Sync changes to original_rows to keep filter state in sync
    if (frm.original_rows) {
        let row = locals[cdt][cdn];
        let idx = frm.original_rows.findIndex(r => r.name === cdn);
        if (idx > -1) {
            frm.original_rows[idx] = Object.assign({}, frm.original_rows[idx], {
                task_name: row.task_name,
                assigned_to: row.assigned_to,
                status: row.status,
                deadline: row.deadline,
                completed_date: row.completed_date
            });
        }
    }
}

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