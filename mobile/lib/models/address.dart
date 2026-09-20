/// Mirrors the backend `AddressRead` schema.
library;

class Address {
  const Address({
    required this.id,
    required this.fullName,
    required this.phone,
    required this.houseNumber,
    required this.street,
    required this.area,
    required this.city,
    required this.state,
    required this.pincode,
    required this.isDefault,
    required this.singleLine,
    this.deliveryInstructions,
  });

  factory Address.fromJson(Map<String, dynamic> json) => Address(
        id: json['id'] as int,
        fullName: json['full_name'] as String,
        phone: json['phone'] as String,
        houseNumber: json['house_number'] as String,
        street: json['street'] as String,
        area: json['area'] as String,
        city: json['city'] as String,
        state: json['state'] as String,
        pincode: json['pincode'] as String,
        isDefault: (json['is_default'] as bool?) ?? false,
        singleLine: json['single_line'] as String,
        deliveryInstructions: json['delivery_instructions'] as String?,
      );

  final int id;
  final String fullName;
  final String phone;
  final String houseNumber;
  final String street;
  final String area;
  final String city;
  final String state;
  final String pincode;
  final bool isDefault;
  final String singleLine;
  final String? deliveryInstructions;

  Map<String, dynamic> toJson() => {
        'full_name': fullName,
        'phone': phone,
        'house_number': houseNumber,
        'street': street,
        'area': area,
        'city': city,
        'state': state,
        'pincode': pincode,
        if (deliveryInstructions != null && deliveryInstructions!.isNotEmpty)
          'delivery_instructions': deliveryInstructions,
      };
}
