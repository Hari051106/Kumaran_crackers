/// Mirrors the backend order schemas.
///
/// Everything here is a snapshot the server took when the order was placed:
/// the prices, the product names and the delivery address are what they were
/// at purchase, not what they are now. The app displays them and never
/// recalculates a total.
library;

import 'package:flutter/material.dart';

import '../core/theme.dart';

/// Where an order has got to.
///
/// `unknown` exists so a status added to the API later is shown using the
/// server's own label rather than silently mislabelled as something else.
enum OrderStatus {
  placed('PLACED'),
  confirmed('CONFIRMED'),
  packing('PACKING'),
  outForDelivery('OUT_FOR_DELIVERY'),
  delivered('DELIVERED'),
  cancelled('CANCELLED'),
  unknown('');

  const OrderStatus(this.wire);

  final String wire;

  static OrderStatus fromJson(String? value) => OrderStatus.values.firstWhere(
        (status) => status.wire == value,
        orElse: () => OrderStatus.unknown,
      );

  bool get isCancelled => this == OrderStatus.cancelled;
  bool get isDelivered => this == OrderStatus.delivered;
}

/// Status is never conveyed by colour alone: every use pairs these with the
/// server's label, so the state is readable without colour vision.
extension OrderStatusLook on OrderStatus {
  IconData get icon => switch (this) {
        OrderStatus.placed => Icons.receipt_long_outlined,
        OrderStatus.confirmed => Icons.check_circle_outline_rounded,
        OrderStatus.packing => Icons.inventory_2_outlined,
        OrderStatus.outForDelivery => Icons.local_shipping_outlined,
        OrderStatus.delivered => Icons.task_alt_rounded,
        OrderStatus.cancelled => Icons.cancel_outlined,
        OrderStatus.unknown => Icons.info_outline_rounded,
      };

  Color get color => switch (this) {
        OrderStatus.delivered => AppTheme.inStock,
        OrderStatus.cancelled => AppTheme.outOfStock,
        OrderStatus.outForDelivery => AppTheme.brand,
        _ => AppTheme.muted,
      };
}

class OrderLine {
  const OrderLine({
    required this.id,
    required this.productId,
    required this.productName,
    required this.productSku,
    required this.quantity,
    required this.unitMrp,
    required this.unitPrice,
    required this.lineTotal,
    required this.lineDiscount,
    this.productImageUrl,
  });

  factory OrderLine.fromJson(Map<String, dynamic> json) => OrderLine(
        id: json['id'] as int,
        productId: json['product_id'] as int,
        productName: json['product_name'] as String,
        productSku: json['product_sku'] as String,
        quantity: json['quantity'] as int,
        unitMrp: json['unit_mrp'] as String,
        unitPrice: json['unit_price'] as String,
        lineTotal: json['line_total'] as String,
        lineDiscount: json['line_discount'] as String,
        productImageUrl: json['product_image_url'] as String?,
      );

  final int id;
  final int productId;
  final String productName;
  final String productSku;
  final int quantity;

  // Decimal strings, frozen at purchase.
  final String unitMrp;
  final String unitPrice;
  final String lineTotal;
  final String lineDiscount;

  final String? productImageUrl;
}

class OrderTotals {
  const OrderTotals({
    required this.subtotal,
    required this.discount,
    required this.itemsTotal,
    required this.deliveryCharge,
    required this.total,
    required this.currency,
  });

  factory OrderTotals.fromJson(Map<String, dynamic> json) => OrderTotals(
        subtotal: json['subtotal'] as String,
        discount: json['discount'] as String,
        itemsTotal: json['items_total'] as String,
        deliveryCharge: json['delivery_charge'] as String,
        total: json['total'] as String,
        currency: (json['currency'] as String?) ?? 'INR',
      );

  final String subtotal;
  final String discount;
  final String itemsTotal;
  final String deliveryCharge;
  final String total;
  final String currency;
}

/// The address as it was when the order was placed. Editing the saved address
/// afterwards does not change where this order went.
class DeliverySnapshot {
  const DeliverySnapshot({
    required this.fullName,
    required this.phone,
    required this.singleLine,
    this.instructions,
  });

  factory DeliverySnapshot.fromJson(Map<String, dynamic> json) => DeliverySnapshot(
        fullName: json['full_name'] as String,
        phone: json['phone'] as String,
        singleLine: json['single_line'] as String,
        instructions: json['instructions'] as String?,
      );

  final String fullName;
  final String phone;
  final String singleLine;
  final String? instructions;
}

/// One stage of the tracking view.
class TimelineStep {
  const TimelineStep({
    required this.status,
    required this.label,
    required this.reached,
    required this.isCurrent,
    this.reachedAt,
  });

  factory TimelineStep.fromJson(Map<String, dynamic> json) => TimelineStep(
        status: OrderStatus.fromJson(json['status'] as String?),
        label: json['label'] as String,
        reached: json['reached'] as bool,
        isCurrent: json['is_current'] as bool,
        reachedAt: _parseTime(json['reached_at'] as String?),
      );

  final OrderStatus status;
  final String label;
  final bool reached;
  final bool isCurrent;
  final DateTime? reachedAt;
}

/// One entry from the server's audit trail.
class OrderEvent {
  const OrderEvent({
    required this.id,
    required this.toStatus,
    required this.createdAt,
    this.fromStatus,
    this.changedByName,
    this.note,
  });

  factory OrderEvent.fromJson(Map<String, dynamic> json) => OrderEvent(
        id: json['id'] as int,
        toStatus: OrderStatus.fromJson(json['to_status'] as String?),
        createdAt: _parseTime(json['created_at'] as String?)!,
        fromStatus: json['from_status'] == null
            ? null
            : OrderStatus.fromJson(json['from_status'] as String?),
        changedByName: json['changed_by_name'] as String?,
        note: json['note'] as String?,
      );

  final int id;
  final OrderStatus toStatus;
  final DateTime createdAt;
  final OrderStatus? fromStatus;
  final String? changedByName;
  final String? note;
}

/// A row in the order history.
class OrderSummary {
  const OrderSummary({
    required this.orderNumber,
    required this.status,
    required this.statusLabel,
    required this.total,
    required this.currency,
    required this.itemCount,
    required this.placedAt,
  });

  factory OrderSummary.fromJson(Map<String, dynamic> json) => OrderSummary(
        orderNumber: json['order_number'] as String,
        status: OrderStatus.fromJson(json['status'] as String?),
        statusLabel: json['status_label'] as String,
        total: json['total'] as String,
        currency: (json['currency'] as String?) ?? 'INR',
        itemCount: json['item_count'] as int,
        placedAt: _parseTime(json['placed_at'] as String?)!,
      );

  final String orderNumber;
  final OrderStatus status;

  /// The server's wording, so a status the app does not know is still readable.
  final String statusLabel;
  final String total;
  final String currency;
  final int itemCount;
  final DateTime placedAt;
}

/// Everything about one order, including its tracking timeline.
class OrderDetail extends OrderSummary {
  const OrderDetail({
    required super.orderNumber,
    required super.status,
    required super.statusLabel,
    required super.total,
    required super.currency,
    required super.itemCount,
    required super.placedAt,
    required this.lines,
    required this.totals,
    required this.deliveryAddress,
    required this.timeline,
    required this.history,
    required this.isCancellableByCustomer,
    this.deliveredAt,
    this.cancelledAt,
    this.cancellationReason,
  });

  factory OrderDetail.fromJson(Map<String, dynamic> json) => OrderDetail(
        orderNumber: json['order_number'] as String,
        status: OrderStatus.fromJson(json['status'] as String?),
        statusLabel: json['status_label'] as String,
        total: json['total'] as String,
        currency: (json['currency'] as String?) ?? 'INR',
        itemCount: json['item_count'] as int,
        placedAt: _parseTime(json['placed_at'] as String?)!,
        lines: (json['items'] as List<dynamic>)
            .map((item) => OrderLine.fromJson(item as Map<String, dynamic>))
            .toList(),
        totals: OrderTotals.fromJson(json['totals'] as Map<String, dynamic>),
        deliveryAddress:
            DeliverySnapshot.fromJson(json['delivery_address'] as Map<String, dynamic>),
        timeline: (json['timeline'] as List<dynamic>)
            .map((step) => TimelineStep.fromJson(step as Map<String, dynamic>))
            .toList(),
        history: (json['status_history'] as List<dynamic>? ?? [])
            .map((event) => OrderEvent.fromJson(event as Map<String, dynamic>))
            .toList(),
        isCancellableByCustomer: (json['is_cancellable_by_customer'] as bool?) ?? false,
        deliveredAt: _parseTime(json['delivered_at'] as String?),
        cancelledAt: _parseTime(json['cancelled_at'] as String?),
        cancellationReason: json['cancellation_reason'] as String?,
      );

  final List<OrderLine> lines;
  final OrderTotals totals;
  final DeliverySnapshot deliveryAddress;
  final List<TimelineStep> timeline;
  final List<OrderEvent> history;

  /// The server's own answer, not a rule re-implemented here.
  final bool isCancellableByCustomer;
  final DateTime? deliveredAt;
  final DateTime? cancelledAt;
  final String? cancellationReason;
}

/// The API sends UTC; the shopper reads local time.
DateTime? _parseTime(String? value) =>
    value == null ? null : DateTime.parse(value).toLocal();
