(function () {
    'use strict';

    window.addEventListener('load', function () {
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

        if ($customer.length === 0) {
            return;
        }

        console.log('Chained dropdowns initialized');

        // Store initial values (for form reload/validation errors)
        var initialSiteId = $site.val();
        var initialOrderId = $salesOrder.val();
        var initialItemId = $orderItem.val();
        var initialCustomerId = $customer.val();

        // If customer is already selected (edit mode or validation error), load dependents
        if (initialCustomerId) {
            loadSites(initialCustomerId, initialSiteId);
            loadOrders(initialCustomerId, initialOrderId, initialItemId);
        }

        // Customer change handler
        $customer.on('change', function () {
            var customerId = $(this).val();

            // Clear dependent fields
            clearDropdown($site, '--- Select Site ---');
            clearDropdown($salesOrder, '--- Select Order (Optional) ---');
            clearDropdown($orderItem, '--- Select Item ---');

            if (customerId) {
                loadSites(customerId, null);
                loadOrders(customerId, null, null);
            }
        });

        // Sales Order change handler
        $salesOrder.on('change', function () {
            var orderId = $(this).val();
            clearDropdown($orderItem, '--- Select Item ---');

            if (orderId) {
                loadOrderItems(orderId, null);
            }
        });

        // Helper function to clear dropdown
        function clearDropdown($el, placeholder) {
            if ($el.length) {
                $el.empty().append('<option value="">' + placeholder + '</option>');
                // Trigger change for Select2 to update
                $el.trigger('change.select2');
            }
        }

        // Load sites for customer
        function loadSites(customerId, selectedSiteId) {
            if (!$site.length) return;

            $.ajax({
                url: '/erp/ajax/customer-sites/',
                data: { customer_id: customerId },
                dataType: 'json',
                success: function (data) {
                    // Keep current selection if exists, otherwise clear
                    var currentVal = $site.val();
                    $site.empty().append('<option value="">--- Select Site ---</option>');

                    $.each(data, function (i, item) {
                        var selected = (selectedSiteId && item.id == selectedSiteId) ? ' selected' : '';
                        $site.append('<option value="' + item.id + '"' + selected + '>' + item.name + '</option>');
                    });

                    // If we had a selected value, restore it
                    if (selectedSiteId) {
                        $site.val(selectedSiteId);
                    }
                    $site.trigger('change.select2');
                }
            });
        }

        // Load orders for customer
        function loadOrders(customerId, selectedOrderId, selectedItemId) {
            if (!$salesOrder.length) return;

            $.ajax({
                url: '/erp/ajax/customer-orders/',
                data: { customer_id: customerId },
                dataType: 'json',
                success: function (data) {
                    $salesOrder.empty().append('<option value="">--- Select Order (Optional) ---</option>');

                    $.each(data, function (i, item) {
                        var selected = (selectedOrderId && item.id == selectedOrderId) ? ' selected' : '';
                        $salesOrder.append('<option value="' + item.id + '"' + selected + '>' + item.name + '</option>');
                    });

                    if (selectedOrderId) {
                        $salesOrder.val(selectedOrderId);
                        // Also load order items if order was selected
                        loadOrderItems(selectedOrderId, selectedItemId);
                    }
                    $salesOrder.trigger('change.select2');
                }
            });
        }

        // Load items for order
        function loadOrderItems(orderId, selectedItemId) {
            if (!$orderItem.length) return;

            $.ajax({
                url: '/erp/ajax/order-items/',
                data: { order_id: orderId },
                dataType: 'json',
                success: function (data) {
                    $orderItem.empty().append('<option value="">--- Select Item ---</option>');

                    $.each(data, function (i, item) {
                        var selected = (selectedItemId && item.id == selectedItemId) ? ' selected' : '';
                        $orderItem.append('<option value="' + item.id + '"' + selected + '>' + item.name + '</option>');
                    });

                    if (selectedItemId) {
                        $orderItem.val(selectedItemId);
                    }
                    $orderItem.trigger('change.select2');
                }
            });
        }
    }
})();