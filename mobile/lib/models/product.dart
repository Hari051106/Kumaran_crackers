/// Mirrors the backend `ProductListItem` / `ProductDetail` schemas.
///
/// Money arrives as an exact decimal STRING and is kept as one. Parsing it into
/// a `double` would reintroduce the rounding error the backend's Decimal
/// columns exist to prevent. Format it with `core/money.dart`.
library;

enum StockStatus {
  inStock,
  lowStock,
  outOfStock;

  static StockStatus fromJson(String? value) => switch (value) {
        'IN_STOCK' => StockStatus.inStock,
        'LOW_STOCK' => StockStatus.lowStock,
        _ => StockStatus.outOfStock,
      };

  String get label => switch (this) {
        StockStatus.inStock => 'In stock',
        StockStatus.lowStock => 'Only a few left',
        StockStatus.outOfStock => 'Out of stock',
      };
}

class ProductImage {
  const ProductImage({required this.id, required this.imageUrl, this.altText});

  factory ProductImage.fromJson(Map<String, dynamic> json) => ProductImage(
        id: json['id'] as int,
        imageUrl: json['image_url'] as String,
        altText: json['alt_text'] as String?,
      );

  final int id;
  final String imageUrl;
  final String? altText;
}

class ProductCategory {
  const ProductCategory({required this.id, required this.name, required this.slug});

  factory ProductCategory.fromJson(Map<String, dynamic> json) => ProductCategory(
        id: json['id'] as int,
        name: json['name'] as String,
        slug: json['slug'] as String,
      );

  final int id;
  final String name;
  final String slug;
}

class Product {
  const Product({
    required this.id,
    required this.name,
    required this.slug,
    required this.sku,
    required this.category,
    required this.mrp,
    required this.sellingPrice,
    required this.discountPercentage,
    required this.discountAmount,
    required this.stockStatus,
    required this.inStock,
    this.primaryImageUrl,
    this.isFeatured = false,
    this.description,
    this.stockQuantity,
    this.images = const [],
  });

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: json['id'] as int,
        name: json['name'] as String,
        slug: json['slug'] as String,
        sku: json['sku'] as String,
        category: ProductCategory.fromJson(json['category'] as Map<String, dynamic>),
        // Deliberately read as String, never num.
        mrp: json['mrp'] as String,
        sellingPrice: json['selling_price'] as String,
        discountPercentage: json['discount_percentage'] as String,
        discountAmount: json['discount_amount'] as String,
        stockStatus: StockStatus.fromJson(json['stock_status'] as String?),
        inStock: (json['in_stock'] as bool?) ?? false,
        primaryImageUrl: json['primary_image_url'] as String?,
        isFeatured: (json['is_featured'] as bool?) ?? false,
        description: json['description'] as String?,
        stockQuantity: json['stock_quantity'] as int?,
        images: (json['images'] as List<dynamic>?)
                ?.map((image) => ProductImage.fromJson(image as Map<String, dynamic>))
                .toList() ??
            const [],
      );

  final int id;
  final String name;
  final String slug;
  final String sku;
  final ProductCategory category;
  final String mrp;
  final String sellingPrice;
  final String discountPercentage;
  final String discountAmount;
  final StockStatus stockStatus;
  final bool inStock;
  final String? primaryImageUrl;
  final bool isFeatured;

  // Detail-only fields.
  final String? description;
  final int? stockQuantity;
  final List<ProductImage> images;

  /// Every image URL for the gallery, falling back to the card image.
  List<String> get galleryUrls {
    if (images.isNotEmpty) return images.map((image) => image.imageUrl).toList();
    final primary = primaryImageUrl;
    return primary == null ? const [] : [primary];
  }

  /// How many units a shopper may put in the basket at once.
  int get maxSelectableQuantity {
    final available = stockQuantity;
    if (available == null) return inStock ? 10 : 0;
    return available < 10 ? available : 10;
  }
}
