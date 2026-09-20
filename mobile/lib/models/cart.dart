/// Mirrors the backend cart and checkout schemas.
///
/// Every money field is an exact decimal STRING computed by the server. The
/// app never calculates a total: it displays what the backend says, so the
/// figure on screen is always the figure that will be charged.
library;

import 'address.dart';
import 'product.dart';

class CartProduct {
  const CartProduct({
    required this.id,
    required this.name,
    required this.slug,
    required this.sku,
    required this.categoryName,
    required this.stockStatus,
    this.primaryImageUrl,
  });

  factory CartProduct.fromJson(Map<String, dynamic> json) => CartProduct(
        id: json['id'] as int,
        name: json['name'] as String,
        slug: json['slug'] as String,
        sku: json['sku'] as String,
        categoryName: (json['category'] as Map<String, dynamic>)['name'] as String,
        stockStatus: StockStatus.fromJson(json['stock_status'] as String?),
        primaryImageUrl: json['primary_image_url'] as String?,
      );

  final int id;
  final String name;
  final String slug;
  final String sku;
  final String categoryName;
  final StockStatus stockStatus;
  final String? primaryImageUrl;
}

class CartLine {
  const CartLine({
    required this.id,
    required this.product,
    required this.quantity,
    required this.unitMrp,
    required this.unitPrice,
    required this.lineMrpTotal,
    required this.lineTotal,
    required this.lineDiscount,
    required this.availableQuantity,
    this.problem,
  });

  factory CartLine.fromJson(Map<String, dynamic> json) => CartLine(
        id: json['id'] as int,
        product: CartProduct.fromJson(json['product'] as Map<String, dynamic>),
        quantity: json['quantity'] as int,
        unitMrp: json['unit_mrp'] as String,
        unitPrice: json['unit_price'] as String,
        lineMrpTotal: json['line_mrp_total'] as String,
        lineTotal: json['line_total'] as String,
        lineDiscount: json['line_discount'] as String,
        availableQuantity: (json['available_quantity'] as int?) ?? 0,
        problem: json['problem'] as String?,
      );

  final int id;
  final CartProduct product;
  final int quantity;

  // Decimal strings.
  final String unitMrp;
  final String unitPrice;
  final String lineMrpTotal;
  final String lineTotal;
  final String lineDiscount;

  /// Units still on the shelf, so the stepper can cap itself.
  final int availableQuantity;

  /// Why this line cannot be bought right now, if it cannot.
  final String? problem;

  bool get hasProblem => problem != null;
}

class BasketTotals {
  const BasketTotals({
    required this.subtotal,
    required this.discount,
    required this.itemsTotal,
    required this.deliveryCharge,
    required this.total,
    required this.freeDeliveryApplied,
    required this.amountToFreeDelivery,
    required this.currency,
  });

  factory BasketTotals.fromJson(Map<String, dynamic> json) => BasketTotals(
        subtotal: json['subtotal'] as String,
        discount: json['discount'] as String,
        itemsTotal: json['items_total'] as String,
        deliveryCharge: json['delivery_charge'] as String,
        total: json['total'] as String,
        freeDeliveryApplied: (json['free_delivery_applied'] as bool?) ?? false,
        amountToFreeDelivery: json['amount_to_free_delivery'] as String,
        currency: (json['currency'] as String?) ?? 'INR',
      );

  final String subtotal;
  final String discount;
  final String itemsTotal;
  final String deliveryCharge;
  final String total;
  final bool freeDeliveryApplied;
  final String amountToFreeDelivery;
  final String currency;
}

class Cart {
  const Cart({
    required this.lines,
    required this.totals,
    required this.itemCount,
    required this.isEmpty,
    required this.isPurchasable,
    this.problems = const [],
  });

  factory Cart.fromJson(Map<String, dynamic> json) => Cart(
        lines: (json['lines'] as List<dynamic>)
            .map((line) => CartLine.fromJson(line as Map<String, dynamic>))
            .toList(),
        totals: BasketTotals.fromJson(json['totals'] as Map<String, dynamic>),
        itemCount: json['item_count'] as int,
        isEmpty: json['is_empty'] as bool,
        isPurchasable: json['is_purchasable'] as bool,
        problems: (json['problems'] as List<dynamic>? ?? [])
            .map((problem) => problem as String)
            .toList(),
      );

  final List<CartLine> lines;
  final BasketTotals totals;
  final int itemCount;
  final bool isEmpty;
  final bool isPurchasable;
  final List<String> problems;

  bool get isNotEmpty => !isEmpty;
}

class CheckoutQuote {
  const CheckoutQuote({
    required this.cart,
    required this.deliveryAddress,
    required this.canPlaceOrder,
    this.blockers = const [],
  });

  factory CheckoutQuote.fromJson(Map<String, dynamic> json) => CheckoutQuote(
        cart: Cart.fromJson(json['cart'] as Map<String, dynamic>),
        deliveryAddress: Address.fromJson(json['delivery_address'] as Map<String, dynamic>),
        canPlaceOrder: json['can_place_order'] as bool,
        blockers: (json['blockers'] as List<dynamic>? ?? [])
            .map((blocker) => blocker as String)
            .toList(),
      );

  final Cart cart;
  final Address deliveryAddress;
  final bool canPlaceOrder;
  final List<String> blockers;
}
