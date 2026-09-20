/// Order parsing, date formatting, and the tracking view.
///
/// The order screens display a snapshot the server took at purchase. These
/// tests pin that contract: money stays an exact string, timestamps become
/// local time, and an unknown status is shown using the server's own label
/// rather than being guessed at.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kumaran_crackers/core/dates.dart';
import 'package:kumaran_crackers/core/theme.dart';
import 'package:kumaran_crackers/models/order.dart';
import 'package:kumaran_crackers/widgets/order_status_chip.dart';

Map<String, dynamic> orderJson({
  String status = 'PLACED',
  String statusLabel = 'Order placed',
  bool cancellable = true,
  String? cancelledAt,
  String? cancellationReason,
}) =>
    {
      'order_number': 'KC-000123',
      'status': status,
      'status_label': statusLabel,
      'total': '1949.25',
      'currency': 'INR',
      'item_count': 3,
      'placed_at': '2026-09-20T09:30:00Z',
      'items': [
        {
          'id': 5,
          'product_id': 11,
          'product_name': 'Thunder King 12-Shot',
          'product_sku': 'PRE-THUNDER-KING',
          'product_image_url': 'https://cdn.example.com/a.jpg',
          'quantity': 2,
          'unit_mrp': '2499.00',
          'unit_price': '1874.25',
          'line_total': '3748.50',
          'line_discount': '1249.50',
        },
      ],
      'totals': {
        'subtotal': '4998.00',
        'discount': '1249.50',
        'items_total': '3748.50',
        'delivery_charge': '0.00',
        'total': '3748.50',
        'currency': 'INR',
      },
      'delivery_address': {
        'full_name': 'Priya Selvam',
        'phone': '9876543210',
        'house_number': '12A',
        'street': 'Anna Salai',
        'area': 'T Nagar',
        'city': 'Chennai',
        'state': 'Tamil Nadu',
        'pincode': '600017',
        'instructions': 'Ring the bell twice',
        'single_line': '12A, Anna Salai, T Nagar, Chennai, Tamil Nadu 600017',
      },
      'timeline': [
        {
          'status': 'PLACED',
          'label': 'Order placed',
          'reached': true,
          'is_current': true,
          'reached_at': '2026-09-20T09:30:00Z',
        },
        {
          'status': 'CONFIRMED',
          'label': 'Confirmed',
          'reached': false,
          'is_current': false,
          'reached_at': null,
        },
      ],
      'status_history': [
        {
          'id': 1,
          'from_status': null,
          'to_status': 'PLACED',
          'changed_by_name': 'Ravi Kumar',
          'note': 'Order placed.',
          'created_at': '2026-09-20T09:30:00Z',
        },
      ],
      'is_cancellable_by_customer': cancellable,
      'delivered_at': null,
      'cancelled_at': cancelledAt,
      'cancellation_reason': cancellationReason,
    };

void main() {
  group('OrderDetail', () {
    test('keeps every money field as the exact string the API sent', () {
      final order = OrderDetail.fromJson(orderJson());

      expect(order.total, '1949.25');
      expect(order.totals.itemsTotal, '3748.50');
      expect(order.lines.single.unitPrice, '1874.25');
      // A num here would mean precision was lost before anything was drawn.
      expect(order.totals.total, isA<String>());
    });

    test('parses the frozen product details', () {
      final line = OrderDetail.fromJson(orderJson()).lines.single;

      expect(line.productName, 'Thunder King 12-Shot');
      expect(line.productSku, 'PRE-THUNDER-KING');
      expect(line.quantity, 2);
    });

    test('converts timestamps to local time', () {
      final order = OrderDetail.fromJson(orderJson());

      expect(order.placedAt.isUtc, isFalse);
      expect(
        order.placedAt.toUtc(),
        DateTime.utc(2026, 9, 20, 9, 30),
      );
    });

    test('takes cancellability from the server, not from a local rule', () {
      expect(
        OrderDetail.fromJson(orderJson(cancellable: false)).isCancellableByCustomer,
        isFalse,
      );
      expect(
        OrderDetail.fromJson(orderJson()).isCancellableByCustomer,
        isTrue,
      );
    });

    test('reads a cancelled order', () {
      final order = OrderDetail.fromJson(
        orderJson(
          status: 'CANCELLED',
          statusLabel: 'Cancelled',
          cancellable: false,
          cancelledAt: '2026-09-20T10:00:00Z',
          cancellationReason: 'Changed my mind',
        ),
      );

      expect(order.status, OrderStatus.cancelled);
      expect(order.status.isCancelled, isTrue);
      expect(order.cancellationReason, 'Changed my mind');
      expect(order.cancelledAt, isNotNull);
    });

    test('parses the tracking timeline', () {
      final timeline = OrderDetail.fromJson(orderJson()).timeline;

      expect(timeline.first.status, OrderStatus.placed);
      expect(timeline.first.reached, isTrue);
      expect(timeline.first.isCurrent, isTrue);
      expect(timeline.last.reached, isFalse);
      expect(timeline.last.reachedAt, isNull);
    });

    test('parses the audit trail', () {
      final history = OrderDetail.fromJson(orderJson()).history;

      expect(history.single.toStatus, OrderStatus.placed);
      expect(history.single.fromStatus, isNull);
      expect(history.single.changedByName, 'Ravi Kumar');
    });
  });

  group('OrderStatus', () {
    test('maps every status the API documents', () {
      expect(OrderStatus.fromJson('PLACED'), OrderStatus.placed);
      expect(OrderStatus.fromJson('CONFIRMED'), OrderStatus.confirmed);
      expect(OrderStatus.fromJson('PACKING'), OrderStatus.packing);
      expect(OrderStatus.fromJson('OUT_FOR_DELIVERY'), OrderStatus.outForDelivery);
      expect(OrderStatus.fromJson('DELIVERED'), OrderStatus.delivered);
      expect(OrderStatus.fromJson('CANCELLED'), OrderStatus.cancelled);
    });

    test('does not mislabel a status it has never seen', () {
      // Guessing "placed" here would tell the shopper something untrue.
      expect(OrderStatus.fromJson('RETURNED'), OrderStatus.unknown);
      expect(OrderStatus.fromJson(null), OrderStatus.unknown);
    });

    test('an unknown status still reads correctly from the server label', () {
      final order = OrderDetail.fromJson(
        orderJson(status: 'RETURNED', statusLabel: 'Returned'),
      );

      expect(order.status, OrderStatus.unknown);
      expect(order.statusLabel, 'Returned');
    });
  });

  group('Dates', () {
    test('formats a date and a time the way the screens show them', () {
      final when = DateTime(2026, 9, 20, 15, 4);

      expect(formatDate(when), '20 Sep 2026');
      expect(formatTime(when), '3:04 pm');
      expect(formatDateTime(when), '20 Sep 2026, 3:04 pm');
    });

    test('handles both ends of the 12-hour clock', () {
      expect(formatTime(DateTime(2026, 1, 1, 0, 5)), '12:05 am');
      expect(formatTime(DateTime(2026, 1, 1, 12, 0)), '12:00 pm');
      expect(formatTime(DateTime(2026, 1, 1, 23, 59)), '11:59 pm');
    });

    test('describes recent moments relatively and older ones by date', () {
      final now = DateTime(2026, 9, 20, 15, 0);

      expect(formatRelative(now.subtract(const Duration(seconds: 20)), now: now), 'Just now');
      expect(formatRelative(now.subtract(const Duration(minutes: 1)), now: now), '1 minute ago');
      expect(formatRelative(now.subtract(const Duration(minutes: 40)), now: now), '40 minutes ago');
      expect(formatRelative(now.subtract(const Duration(hours: 3)), now: now), '3 hours ago');
      expect(
        formatRelative(now.subtract(const Duration(days: 1)), now: now),
        startsWith('Yesterday'),
      );
      expect(formatRelative(now.subtract(const Duration(days: 3)), now: now), '3 days ago');
      expect(formatRelative(DateTime(2026, 1, 4, 9, 0), now: now), '4 Jan 2026');
    });
  });

  group('OrderStatusChip', () {
    testWidgets('always pairs colour with an icon and words', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: OrderStatusChip(status: OrderStatus.delivered, label: 'Delivered'),
          ),
        ),
      );

      // Red and green are close to indistinguishable under deuteranopia, so
      // the state must never be carried by colour alone.
      expect(find.text('Delivered'), findsOneWidget);
      expect(find.byIcon(Icons.task_alt_rounded), findsOneWidget);
    });

    testWidgets('shows the server label for a status it does not know', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: OrderStatusChip(status: OrderStatus.unknown, label: 'Returned'),
          ),
        ),
      );

      expect(find.text('Returned'), findsOneWidget);
    });
  });
}
