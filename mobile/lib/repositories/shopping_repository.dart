/// Cart, address and checkout calls.
///
/// Requests carry product ids, quantities and address ids. Nothing about
/// money is ever sent: the server decides what things cost.
library;

import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/address.dart';
import '../models/cart.dart';

class ShoppingRepository {
  ShoppingRepository(this._client);

  final ApiClient _client;

  // ---- Cart -----------------------------------------------------------------
  Future<Cart> cart() async {
    try {
      final response = await _client.dio.get<Map<String, dynamic>>('/cart');
      return Cart.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Cart> addItem({required int productId, int quantity = 1}) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/cart/items',
        data: {'product_id': productId, 'quantity': quantity},
      );
      return Cart.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Cart> setQuantity({required int lineId, required int quantity}) async {
    try {
      final response = await _client.dio.patch<Map<String, dynamic>>(
        '/cart/items/$lineId',
        data: {'quantity': quantity},
      );
      return Cart.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Cart> removeItem(int lineId) async {
    try {
      final response = await _client.dio.delete<Map<String, dynamic>>('/cart/items/$lineId');
      return Cart.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Cart> clear() async {
    try {
      final response = await _client.dio.delete<Map<String, dynamic>>('/cart');
      return Cart.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  // ---- Addresses ------------------------------------------------------------
  Future<List<Address>> addresses() async {
    try {
      final response = await _client.dio.get<List<dynamic>>('/addresses');
      return response.data!
          .map((item) => Address.fromJson(item as Map<String, dynamic>))
          .toList();
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Address> createAddress(Map<String, dynamic> payload) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/addresses',
        data: payload,
      );
      return Address.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Address> updateAddress(int id, Map<String, dynamic> payload) async {
    try {
      final response = await _client.dio.patch<Map<String, dynamic>>(
        '/addresses/$id',
        data: payload,
      );
      return Address.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Address> setDefaultAddress(int id) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>('/addresses/$id/default');
      return Address.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<void> deleteAddress(int id) async {
    try {
      await _client.dio.delete<void>('/addresses/$id');
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  // ---- Checkout -------------------------------------------------------------
  Future<CheckoutQuote> quote(int addressId) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/checkout/quote',
        data: {'address_id': addressId},
      );
      return CheckoutQuote.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }
}
