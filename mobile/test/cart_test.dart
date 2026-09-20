/// The app must render the server's money exactly, and never recompute it.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:kumaran_crackers/core/money.dart';
import 'package:kumaran_crackers/models/address.dart';
import 'package:kumaran_crackers/models/cart.dart';
import 'package:kumaran_crackers/models/product.dart';

Map<String, dynamic> lineJson({
  int id = 1,
  int quantity = 2,
  String unitMrp = '250.00',
  String unitPrice = '199.00',
  String lineTotal = '398.00',
  String lineDiscount = '102.00',
  int available = 50,
  String? problem,
}) =>
    {
      'id': id,
      'product': {
        'id': 7,
        'name': 'Colour Sparkler 30cm',
        'slug': 'colour-sparkler-30cm',
        'sku': 'SPK-001',
        'category': {'id': 1, 'name': 'Sparklers', 'slug': 'sparklers'},
        'stock_status': 'IN_STOCK',
        'primary_image_url': null,
      },
      'quantity': quantity,
      'unit_mrp': unitMrp,
      'unit_price': unitPrice,
      'line_mrp_total': '500.00',
      'line_total': lineTotal,
      'line_discount': lineDiscount,
      'available_quantity': available,
      'problem': problem,
    };

Map<String, dynamic> cartJson({
  List<Map<String, dynamic>>? lines,
  String subtotal = '500.00',
  String discount = '102.00',
  String itemsTotal = '398.00',
  String delivery = '50.00',
  String total = '448.00',
  bool freeDelivery = false,
  String toFree = '1602.00',
  bool purchasable = true,
  List<String> problems = const [],
}) =>
    {
      'lines': lines ?? [lineJson()],
      'totals': {
        'subtotal': subtotal,
        'discount': discount,
        'items_total': itemsTotal,
        'delivery_charge': delivery,
        'total': total,
        'free_delivery_applied': freeDelivery,
        'amount_to_free_delivery': toFree,
        'currency': 'INR',
      },
      'item_count': (lines ?? [lineJson()]).fold<int>(
        0,
        (sum, line) => sum + (line['quantity'] as int),
      ),
      'is_empty': (lines ?? [lineJson()]).isEmpty,
      'is_purchasable': purchasable,
      'problems': problems,
    };

void main() {
  group('Cart parsing', () {
    test('keeps every money field as the exact string the server sent', () {
      final cart = Cart.fromJson(cartJson());

      expect(cart.totals.subtotal, '500.00');
      expect(cart.totals.total, '448.00');
      expect(cart.lines.first.lineTotal, '398.00');
      // A num here would mean precision was already lost.
      expect(cart.totals.total, isA<String>());
      expect(cart.lines.first.unitPrice, isA<String>());
    });

    test('reads the item count from the server rather than recomputing it', () {
      final cart = Cart.fromJson(
        cartJson(lines: [lineJson(id: 1, quantity: 2), lineJson(id: 2, quantity: 3)]),
      );
      expect(cart.itemCount, 5);
      expect(cart.lines, hasLength(2));
    });

    test('an empty basket parses cleanly', () {
      final cart = Cart.fromJson(
        cartJson(
          lines: [],
          subtotal: '0.00',
          discount: '0.00',
          itemsTotal: '0.00',
          delivery: '0.00',
          total: '0.00',
          purchasable: false,
        ),
      );
      expect(cart.isEmpty, isTrue);
      expect(cart.isPurchasable, isFalse);
      expect(cart.itemCount, 0);
    });

    test('carries the per-line problem through', () {
      final cart = Cart.fromJson(
        cartJson(
          lines: [lineJson(problem: 'Only 2 units remain.', available: 2)],
          purchasable: false,
          problems: const ['Only 2 units remain.'],
        ),
      );
      expect(cart.lines.first.hasProblem, isTrue);
      expect(cart.lines.first.availableQuantity, 2);
      expect(cart.isPurchasable, isFalse);
      expect(cart.problems, hasLength(1));
    });

    test('reads the free-delivery flags', () {
      final cart = Cart.fromJson(
        cartJson(delivery: '0.00', total: '2500.00', freeDelivery: true, toFree: '0.00'),
      );
      expect(cart.totals.freeDeliveryApplied, isTrue);
      expect(cart.totals.deliveryCharge, '0.00');
    });

    test('a line with no discount parses', () {
      final cart = Cart.fromJson(
        cartJson(lines: [lineJson(lineDiscount: '0.00', unitMrp: '199.00')]),
      );
      expect(compareMoney(cart.lines.first.lineDiscount, '0.00'), 0);
    });

    test('the stock status maps onto the shared enum', () {
      final cart = Cart.fromJson(cartJson());
      expect(cart.lines.first.product.stockStatus, StockStatus.inStock);
    });
  });

  group('Displaying totals', () {
    test('formats the payable amount exactly as sent', () {
      final cart = Cart.fromJson(cartJson(total: '1874.25'));
      expect(formatMoney(cart.totals.total), '₹1,874.25');
    });

    test('formats a large total with Indian grouping', () {
      final cart = Cart.fromJson(cartJson(total: '140568.75'));
      expect(formatMoney(cart.totals.total), '₹1,40,568.75');
    });
  });

  group('CheckoutQuote', () {
    Map<String, dynamic> quoteJson({
      bool canPlace = true,
      List<String> blockers = const [],
    }) =>
        {
          'cart': cartJson(purchasable: canPlace),
          'delivery_address': {
            'id': 3,
            'full_name': 'Priya Selvam',
            'phone': '9876543210',
            'house_number': '12A',
            'street': 'Anna Salai',
            'area': 'T Nagar',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600017',
            'is_default': true,
            'single_line': '12A, Anna Salai, T Nagar, Chennai, Tamil Nadu, 600017',
            'delivery_instructions': null,
          },
          'can_place_order': canPlace,
          'blockers': blockers,
        };

    test('parses a quote that is ready to order', () {
      final quote = CheckoutQuote.fromJson(quoteJson());
      expect(quote.canPlaceOrder, isTrue);
      expect(quote.blockers, isEmpty);
      expect(quote.deliveryAddress.city, 'Chennai');
      expect(quote.cart.totals.total, '448.00');
    });

    test('carries the blockers when an order cannot be placed', () {
      final quote = CheckoutQuote.fromJson(
        quoteJson(canPlace: false, blockers: const ['Your basket is empty.']),
      );
      expect(quote.canPlaceOrder, isFalse);
      expect(quote.blockers.first, 'Your basket is empty.');
    });
  });

  group('Address', () {
    test('parses and exposes the single-line form', () {
      final address = Address.fromJson({
        'id': 3,
        'full_name': 'Priya Selvam',
        'phone': '9876543210',
        'house_number': '12A',
        'street': 'Anna Salai',
        'area': 'T Nagar',
        'city': 'Chennai',
        'state': 'Tamil Nadu',
        'pincode': '600017',
        'is_default': true,
        'single_line': '12A, Anna Salai, T Nagar, Chennai, Tamil Nadu, 600017',
        'delivery_instructions': 'Ring twice',
      });

      expect(address.isDefault, isTrue);
      expect(address.singleLine, contains('600017'));
      expect(address.deliveryInstructions, 'Ring twice');
    });

    test('serialises only the fields the server accepts', () {
      final address = Address.fromJson({
        'id': 3,
        'full_name': 'Priya Selvam',
        'phone': '9876543210',
        'house_number': '12A',
        'street': 'Anna Salai',
        'area': 'T Nagar',
        'city': 'Chennai',
        'state': 'Tamil Nadu',
        'pincode': '600017',
        'is_default': true,
        'single_line': 'x',
        'delivery_instructions': null,
      });

      final json = address.toJson();
      // Server-owned fields are never sent back.
      expect(json.containsKey('id'), isFalse);
      expect(json.containsKey('single_line'), isFalse);
      expect(json.containsKey('delivery_instructions'), isFalse);
      expect(json['pincode'], '600017');
    });
  });
}
