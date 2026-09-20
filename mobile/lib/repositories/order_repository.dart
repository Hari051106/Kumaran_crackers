/// Order calls.
///
/// Placing an order sends only the chosen address: the basket is already on
/// the server and the price is the server's to decide. Nothing about money is
/// ever sent from here.
library;

import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../models/order.dart';
import '../models/paged.dart';

class OrderRepository {
  OrderRepository(this._client);

  final ApiClient _client;

  Future<OrderDetail> place(int addressId) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/orders',
        data: {'address_id': addressId},
      );
      return OrderDetail.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<Paged<OrderSummary>> myOrders({int page = 1, int pageSize = 20}) async {
    try {
      final response = await _client.dio.get<Map<String, dynamic>>(
        '/orders',
        queryParameters: {'page': page, 'page_size': pageSize},
      );
      return Paged.fromJson(response.data!, OrderSummary.fromJson);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<OrderDetail> detail(String orderNumber) async {
    try {
      final response =
          await _client.dio.get<Map<String, dynamic>>('/orders/$orderNumber');
      return OrderDetail.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<OrderDetail> cancel(String orderNumber, {String? reason}) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/orders/$orderNumber/cancel',
        data: {if (reason != null && reason.isNotEmpty) 'reason': reason},
      );
      return OrderDetail.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }
}
