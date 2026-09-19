/// Mirrors the backend `CategoryRead` / `CategoryWithCount` schemas.
library;

class Category {
  const Category({
    required this.id,
    required this.name,
    required this.slug,
    this.description,
    this.imageUrl,
    this.displayOrder = 0,
    this.productCount = 0,
  });

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as int,
        name: json['name'] as String,
        slug: json['slug'] as String,
        description: json['description'] as String?,
        imageUrl: json['image_url'] as String?,
        displayOrder: (json['display_order'] as int?) ?? 0,
        productCount: (json['product_count'] as int?) ?? 0,
      );

  final int id;
  final String name;
  final String slug;
  final String? description;
  final String? imageUrl;
  final int displayOrder;
  final int productCount;
}
