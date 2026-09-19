/// Parsing must preserve the API contract, especially money as strings.
library;
import 'package:flutter_test/flutter_test.dart';
import 'package:kumaran_crackers/models/category.dart';
import 'package:kumaran_crackers/models/paged.dart';
import 'package:kumaran_crackers/models/product.dart';
import 'package:kumaran_crackers/models/user.dart';

Map<String, dynamic> productJson({
  String mrp = '2499.00',
  String sellingPrice = '1874.25',
  String discountPercentage = '25.0',
  String stockStatus = 'IN_STOCK',
  bool inStock = true,
  int? stockQuantity,
  List<Map<String, dynamic>>? images,
}) =>
    {
      'id': 1,
      'name': 'Thunder King 12-Shot',
      'slug': 'thunder-king-12-shot',
      'sku': 'PRE-THUNDER-KING',
      'category': {'id': 9, 'name': 'Premium Aerial Shells', 'slug': 'premium-aerial-shells'},
      'mrp': mrp,
      'selling_price': sellingPrice,
      'discount_percentage': discountPercentage,
      'discount_amount': '624.75',
      'stock_status': stockStatus,
      'in_stock': inStock,
      'primary_image_url': 'https://cdn.example.com/a.jpg',
      'is_featured': true,
      'is_active': true,
      if (stockQuantity != null) 'stock_quantity': stockQuantity,
      if (images != null) 'images': images,
    };

void main() {
  group('Product', () {
    test('keeps money as the exact string the API sent', () {
      final product = Product.fromJson(productJson());

      expect(product.mrp, '2499.00');
      expect(product.sellingPrice, '1874.25');
      // The types matter: a num here would mean precision was already lost.
      expect(product.mrp, isA<String>());
      expect(product.sellingPrice, isA<String>());
    });

    test('maps stock status', () {
      expect(Product.fromJson(productJson()).stockStatus, StockStatus.inStock);
      expect(
        Product.fromJson(productJson(stockStatus: 'LOW_STOCK')).stockStatus,
        StockStatus.lowStock,
      );
      expect(
        Product.fromJson(productJson(stockStatus: 'OUT_OF_STOCK')).stockStatus,
        StockStatus.outOfStock,
      );
    });

    test('treats an unknown status as out of stock', () {
      // Failing closed is right: better to refuse a sale than oversell.
      expect(
        Product.fromJson(productJson(stockStatus: 'SOMETHING_NEW')).stockStatus,
        StockStatus.outOfStock,
      );
    });

    test('caps the quantity selector at available stock', () {
      expect(Product.fromJson(productJson(stockQuantity: 3)).maxSelectableQuantity, 3);
      // Never offers more than ten at a time, even with plenty on the shelf.
      expect(Product.fromJson(productJson(stockQuantity: 500)).maxSelectableQuantity, 10);
      expect(
        Product.fromJson(productJson(stockQuantity: 0, inStock: false))
            .maxSelectableQuantity,
        0,
      );
    });

    test('builds the gallery from images, falling back to the card image', () {
      final withImages = Product.fromJson(
        productJson(images: [
          {'id': 1, 'image_url': 'https://cdn.example.com/1.jpg', 'alt_text': null},
          {'id': 2, 'image_url': 'https://cdn.example.com/2.jpg', 'alt_text': 'Side'},
        ]),
      );
      expect(withImages.galleryUrls, [
        'https://cdn.example.com/1.jpg',
        'https://cdn.example.com/2.jpg',
      ]);

      expect(Product.fromJson(productJson()).galleryUrls, ['https://cdn.example.com/a.jpg']);
    });

    test('parses a detail payload with description and stock', () {
      final json = productJson(stockQuantity: 40)..['description'] = 'Twelve-shot shell.';
      final product = Product.fromJson(json);
      expect(product.description, 'Twelve-shot shell.');
      expect(product.stockQuantity, 40);
    });
  });

  group('Category', () {
    test('parses, defaulting the product count', () {
      final category = Category.fromJson({
        'id': 1,
        'name': 'Sparklers',
        'slug': 'sparklers',
        'description': 'Hand-held sparklers.',
        'image_url': null,
        'display_order': 1,
      });
      expect(category.name, 'Sparklers');
      expect(category.productCount, 0);
    });
  });

  group('Paged', () {
    test('parses the envelope and its items', () {
      final page = Paged.fromJson({
        'items': [productJson()],
        'meta': {
          'total': 42,
          'page': 1,
          'page_size': 20,
          'total_pages': 3,
          'has_next': true,
          'has_previous': false,
        },
      }, Product.fromJson);

      expect(page.items, hasLength(1));
      expect(page.meta.total, 42);
      expect(page.meta.hasNext, isTrue);
      expect(page.meta.hasPrevious, isFalse);
    });
  });

  group('AppUser', () {
    test('parses and derives initials', () {
      final user = AppUser.fromJson({
        'id': 1,
        'email': 'priya@example.com',
        'full_name': 'Priya Selvam',
        'phone': '9876543210',
        'role': {'id': 3, 'name': 'CUSTOMER', 'description': null},
        'is_verified': false,
      });
      expect(user.fullName, 'Priya Selvam');
      expect(user.roleName, 'CUSTOMER');
      expect(user.initials, 'PS');
    });

    test('handles a single-word name', () {
      final user = AppUser.fromJson({
        'id': 2,
        'email': 'ravi@example.com',
        'full_name': 'Ravi',
        'role': {'id': 3, 'name': 'CUSTOMER', 'description': null},
      });
      expect(user.initials, 'R');
    });
  });
}
