/// Catalogue reads: categories and products.
///
/// These endpoints are public, so the home screen renders before sign-in.
library;

import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../core/config.dart';
import '../models/category.dart';
import '../models/paged.dart';
import '../models/product.dart';

/// Sort orders the catalogue offers, matching the backend's `ProductSort`.
enum ProductSort {
  newest('newest', 'Newest first'),
  priceLowToHigh('price_asc', 'Price: low to high'),
  priceHighToLow('price_desc', 'Price: high to low'),
  nameAtoZ('name_asc', 'Name: A to Z'),
  biggestDiscount('discount', 'Biggest discount');

  const ProductSort(this.value, this.label);

  final String value;
  final String label;
}

class ProductQuery {
  const ProductQuery({
    this.search,
    this.categoryId,
    this.categorySlug,
    this.minPrice,
    this.maxPrice,
    this.inStockOnly = false,
    this.featuredOnly = false,
    this.discountedOnly = false,
    this.sort = ProductSort.newest,
    this.page = 1,
    this.pageSize = AppConfig.pageSize,
  });

  final String? search;
  final int? categoryId;
  final String? categorySlug;

  /// Decimal strings, so the bounds stay exact.
  final String? minPrice;
  final String? maxPrice;

  final bool inStockOnly;
  final bool featuredOnly;
  final bool discountedOnly;
  final ProductSort sort;
  final int page;
  final int pageSize;

  ProductQuery copyWith({
    String? search,
    int? categoryId,
    String? minPrice,
    String? maxPrice,
    bool? inStockOnly,
    ProductSort? sort,
    int? page,
    bool clearCategory = false,
    bool clearPrices = false,
  }) =>
      ProductQuery(
        search: search ?? this.search,
        categoryId: clearCategory ? null : (categoryId ?? this.categoryId),
        categorySlug: clearCategory ? null : categorySlug,
        minPrice: clearPrices ? null : (minPrice ?? this.minPrice),
        maxPrice: clearPrices ? null : (maxPrice ?? this.maxPrice),
        inStockOnly: inStockOnly ?? this.inStockOnly,
        featuredOnly: featuredOnly,
        discountedOnly: discountedOnly,
        sort: sort ?? this.sort,
        page: page ?? this.page,
        pageSize: pageSize,
      );

  Map<String, dynamic> toQueryParameters() => {
        if (search != null && search!.trim().isNotEmpty) 'query': search!.trim(),
        if (categoryId != null) 'category_id': categoryId,
        if (categorySlug != null) 'category': categorySlug,
        if (minPrice != null) 'min_price': minPrice,
        if (maxPrice != null) 'max_price': maxPrice,
        if (inStockOnly) 'in_stock': true,
        if (featuredOnly) 'featured': true,
        if (discountedOnly) 'discounted': true,
        'sort': sort.value,
        'page': page,
        'page_size': pageSize,
      };

  @override
  bool operator ==(Object other) =>
      other is ProductQuery &&
      other.search == search &&
      other.categoryId == categoryId &&
      other.categorySlug == categorySlug &&
      other.minPrice == minPrice &&
      other.maxPrice == maxPrice &&
      other.inStockOnly == inStockOnly &&
      other.featuredOnly == featuredOnly &&
      other.discountedOnly == discountedOnly &&
      other.sort == sort &&
      other.page == page &&
      other.pageSize == pageSize;

  @override
  int get hashCode => Object.hash(
        search,
        categoryId,
        categorySlug,
        minPrice,
        maxPrice,
        inStockOnly,
        featuredOnly,
        discountedOnly,
        sort,
        page,
        pageSize,
      );
}

class CatalogRepository {
  CatalogRepository(this._client);

  final ApiClient _client;

  Future<List<Category>> categories() async {
    try {
      final response = await _client.dio.get<List<dynamic>>('/categories');
      return response.data!
          .map((item) => Category.fromJson(item as Map<String, dynamic>))
          .toList();
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Paged<Product>> products(ProductQuery query) async {
    try {
      final response = await _client.dio.get<Map<String, dynamic>>(
        '/products',
        queryParameters: query.toQueryParameters(),
      );
      return Paged.fromJson(response.data!, Product.fromJson);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Product> productBySlug(String slug) async {
    try {
      final response = await _client.dio.get<Map<String, dynamic>>('/products/$slug');
      return Product.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }
}
