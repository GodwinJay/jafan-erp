(function () {
    'use strict';

    // Wait for page to fully load
    window.addEventListener('load', function () {
        // Give Select2 time to initialize
        setTimeout(initChainedDropdowns, 500);
    });

    function initChainedDropdowns() {
        var $ = django.jQuery;

        if (!$) {
            console.error('django.jQuery not found');
            return;
        }

        var $customer = $('select[name="customer"]');
        var $site = $('select[name="site"]');
        var $salesOrder = $('select[name="sales_order"]');
        var $orderItem = $('select[name="order_item"]');

        // Only run if we're on a page with these fields
        if ($customer.length === 0) {
            return;
        }

        console.log('Chained dropdowns initialized');

        // Customer change handler
        $customer.on('change', function () {
            var customerId = $(this).val();

            // Clear dependent fields
            $site.empty().append('<option value="">--- Select Site ---</option>');
            $salesOrder.empty().append('<option value="">--- Select Order (Optional) ---</option>');
            $orderItem.empty().append('<option value="">--- Select Item ---</option>');

            if (customerId) {
                // Load Sites
                $.ajax({
                    url: '/erp/ajax/customer-sites/',
                    data: { customer_id: customerId },
                    dataType: 'json',
                    success: function (data) {
                        $.each(data, function (i, item) {
                            $site.append('<option value="' + item.id + '">' + item.name + '</option>');
                        });
                    }
                });

                // Load Sales Orders (non-completed only)
                $.ajax({
                    url: '/erp/ajax/customer-orders/',
                    data: { customer_id: customerId },
                    dataType: 'json',
                    success: function (data) {
                        $.each(data, function (i, item) {
                            $salesOrder.append('<option value="' + item.id + '">' + item.name + '</option>');
                        });
                    }
                });
            }
        });

        // Sales Order change handler
        $salesOrder.on('change', function () {
            var orderId = $(this).val();

            // Clear order items
            $orderItem.empty().append('<option value="">--- Select Item ---</option>');

            if (orderId) {
                $.ajax({
                    url: '/erp/ajax/order-items/',
                    data: { order_id: orderId },
                    dataType: 'json',
                    success: function (data) {
                        $.each(data, function (i, item) {
                            $orderItem.append('<option value="' + item.id + '">' + item.name + '</option>');
                        });
                    }
                });
            }
        });
    }
})();