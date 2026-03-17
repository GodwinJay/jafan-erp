window.addEventListener('load', function () {
    'use strict';

    var $ = django.jQuery;
    if (!$) return;

    var customerField = $('#id_customer');
    var orderField = $('#id_sales_order');

    if (customerField.length === 0) return;

    function filterOrders(preserveOrderId) {
        var customerId = customerField.val();

        if (!customerId) {
            orderField.html('<option value="">---------</option>');
            orderField.trigger('change.select2');
            return;
        }

        $.ajax({
            url: '/erp/ajax/customer-orders/',
            data: { 'customer_id': customerId },
            dataType: 'json',
            success: function (data) {
                var options = '<option value="">---------</option>';
                $.each(data, function (index, order) {
                    options += '<option value="' + order.id + '">' + order.name + '</option>';
                });
                orderField.html(options);

                if (preserveOrderId) {
                    orderField.val(preserveOrderId);
                }

                orderField.trigger('change.select2');
            },
            error: function (xhr, status, error) {
                console.error('Error fetching orders:', error);
            }
        });
    }

    customerField.on('change select2:select select2:clear', function () {
        filterOrders(null);
    });

    if (customerField.val()) {
        var currentOrder = orderField.val();
        filterOrders(currentOrder);
    }
});
