// Custom JavaScript for MPHAMVU WATER ENGINEERS Enterprise Management System

// Document ready function
$(document).ready(function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
    
    // Add fade-in animation to cards
    $('.card').addClass('fade-in');
    
    // Form validation
    $('form').on('submit', function(e) {
        var form = $(this);
        if (form[0].checkValidity() === false) {
            e.preventDefault();
            e.stopPropagation();
        }
        form.addClass('was-validated');
    });
    
    // Confirm delete actions
    $('.btn-delete').on('click', function(e) {
        if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
            e.preventDefault();
        }
    });
    
    // Loading state for buttons
    $('.btn-loading').on('click', function() {
        var btn = $(this);
        var originalText = btn.html();
        btn.html('<span class="loading"></span> Loading...');
        btn.prop('disabled', true);
        
        // Simulate loading (remove this in production)
        setTimeout(function() {
            btn.html(originalText);
            btn.prop('disabled', false);
        }, 2000);
    });
    
    // Auto-format currency inputs
    $('.currency-input').on('input', function() {
        var value = $(this).val().replace(/[^0-9.]/g, '');
        $(this).val(value);
    });
    
    // Auto-format phone numbers
    $('.phone-input').on('input', function() {
        var value = $(this).val().replace(/[^0-9+]/g, '');
        $(this).val(value);
    });
    
    // Date picker initialization (if needed)
    $('.date-picker').datepicker({
        format: 'yyyy-mm-dd',
        autoclose: true,
        todayHighlight: true
    });
    
    // Table row click actions
    $('.table-row-clickable').on('click', function() {
        var url = $(this).data('url');
        if (url) {
            window.location.href = url;
        }
    });
    
    // Search functionality
    $('#search-input').on('keyup', function() {
        var value = $(this).val().toLowerCase();
        $('.searchable-row').filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
        });
    });
    
    // Print functionality
    $('.btn-print').on('click', function() {
        window.print();
    });
    
    // Export to Excel functionality (placeholder)
    $('.btn-export-excel').on('click', function() {
        // This would be implemented with a library like SheetJS
        alert('Export to Excel functionality would be implemented here');
    });
    
    // Export to PDF functionality (placeholder)
    $('.btn-export-pdf').on('click', function() {
        // This would be implemented with a library like jsPDF
        alert('Export to PDF functionality would be implemented here');
    });
});

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-MW', {
        style: 'currency',
        currency: 'MWK'
    }).format(amount);
}

function formatDate(date) {
    return new Date(date).toLocaleDateString('en-MW');
}

function showNotification(message, type = 'info') {
    var alertClass = 'alert-' + type;
    var alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    $('#notifications-container').prepend(alertHtml);
    
    // Auto-hide after 5 seconds
    setTimeout(function() {
        $('.alert').first().fadeOut('slow');
    }, 5000);
}

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// AJAX helper functions
function ajaxGet(url, successCallback, errorCallback) {
    $.ajax({
        url: url,
        method: 'GET',
        success: successCallback,
        error: errorCallback || function(xhr, status, error) {
            showNotification('Error: ' + error, 'danger');
        }
    });
}

function ajaxPost(url, data, successCallback, errorCallback) {
    $.ajax({
        url: url,
        method: 'POST',
        data: data,
        success: successCallback,
        error: errorCallback || function(xhr, status, error) {
            showNotification('Error: ' + error, 'danger');
        }
    });
}

// Form validation helpers
function validateEmail(email) {
    var regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

function validatePhone(phone) {
    var regex = /^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}$/;
    return regex.test(phone);
}

function validateRequired(field) {
    return field.trim().length > 0;
}

// Dashboard real-time updates (placeholder)
function updateDashboardStats() {
    // This would be implemented with WebSocket or periodic AJAX calls
    console.log('Updating dashboard stats...');
}

// Initialize periodic updates
setInterval(updateDashboardStats, 30000); // Update every 30 seconds

// Keyboard shortcuts
$(document).on('keydown', function(e) {
    // Ctrl + S for save
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        $('.btn-save').click();
    }
    
    // Ctrl + N for new
    if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        $('.btn-new').click();
    }
    
    // Ctrl + P for print
    if (e.ctrlKey && e.key === 'p') {
        e.preventDefault();
        window.print();
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        $('.modal').modal('hide');
    }
});

// Dark mode toggle (if needed)
function toggleDarkMode() {
    $('body').toggleClass('dark-mode');
    localStorage.setItem('darkMode', $('body').hasClass('dark-mode'));
}

// Load dark mode preference
if (localStorage.getItem('darkMode') === 'true') {
    $('body').addClass('dark-mode');
}

// Print styles
function printElement(elementId) {
    var printContents = document.getElementById(elementId).innerHTML;
    var originalContents = document.body.innerHTML;
    
    document.body.innerHTML = printContents;
    window.print();
    document.body.innerHTML = originalContents;
    
    // Re-initialize JavaScript after print
    location.reload();
}

// Chart helper functions (if Chart.js is used)
function createDoughnutChart(canvasId, data, options) {
    var ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: options
    });
}

function createBarChart(canvasId, data, options) {
    var ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: data,
        options: options
    });
}

function createLineChart(canvasId, data, options) {
    var ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: data,
        options: options
    });
}

// Data table helpers
function sortTable(tableId, column, ascending) {
    var table = document.getElementById(tableId);
    var tbody = table.getElementsByTagName('tbody')[0];
    var rows = Array.from(tbody.getElementsByTagName('tr'));
    
    rows.sort(function(a, b) {
        var aVal = a.getElementsByTagName('td')[column].textContent;
        var bVal = b.getElementsByTagName('td')[column].textContent;
        
        if (ascending) {
            return aVal.localeCompare(bVal);
        } else {
            return bVal.localeCompare(aVal);
        }
    });
    
    rows.forEach(function(row) {
        tbody.appendChild(row);
    });
}

// File upload helpers
function handleFileUpload(input, callback) {
    var file = input.files[0];
    if (file) {
        var reader = new FileReader();
        reader.onload = function(e) {
            callback(e.target.result, file);
        };
        reader.readAsDataURL(file);
    }
}

// Session timeout warning
function checkSessionTimeout() {
    var timeout = 30 * 60 * 1000; // 30 minutes
    var warning = 5 * 60 * 1000; // 5 minutes before timeout
    
    setTimeout(function() {
        showNotification('Your session will expire in 5 minutes. Please save your work.', 'warning');
    }, timeout - warning);
    
    setTimeout(function() {
        window.location.href = '/logout';
    }, timeout);
}

// Initialize session timeout check
checkSessionTimeout();
