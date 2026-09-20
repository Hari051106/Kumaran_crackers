/// Delivery address management: the list, and the add/edit form.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_exception.dart';
import '../../core/theme.dart';
import '../../models/address.dart';
import '../../providers/providers.dart';
import '../../widgets/state_views.dart';

class AddressListScreen extends ConsumerWidget {
  const AddressListScreen({super.key, this.selecting = false});

  /// When true the screen is being used to pick an address for checkout, and
  /// tapping one returns it rather than opening the editor.
  final bool selecting;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final addresses = ref.watch(addressesProvider);

    return Scaffold(
      appBar: AppBar(title: Text(selecting ? 'Choose an address' : 'Delivery addresses')),
      body: addresses.when(
        loading: () => const LoadingView(label: 'Loading your addresses…'),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(addressesProvider),
        ),
        data: (items) {
          if (items.isEmpty) {
            return EmptyView(
              title: 'No saved addresses',
              message: 'Add one so we know where to deliver your order.',
              icon: Icons.location_on_outlined,
              action: FilledButton(
                onPressed: () => context.push('/addresses/new'),
                child: const Text('Add an address'),
              ),
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
            itemCount: items.length,
            itemBuilder: (context, index) => _AddressCard(
              address: items[index],
              selecting: selecting,
              onSetDefault: () => _setDefault(context, ref, items[index]),
              onDelete: () => _confirmDelete(context, ref, items[index]),
            ),
          );
        },
      ),
      floatingActionButton: addresses.maybeWhen(
        data: (items) => items.isEmpty
            ? null
            : FloatingActionButton.extended(
                key: const Key('add-address'),
                backgroundColor: AppTheme.brand,
                foregroundColor: Colors.white,
                onPressed: () => context.push('/addresses/new'),
                icon: const Icon(Icons.add_rounded),
                label: const Text('Add address'),
              ),
        orElse: () => null,
      ),
    );
  }

  Future<void> _setDefault(BuildContext context, WidgetRef ref, Address address) async {
    try {
      await ref.read(shoppingRepositoryProvider).setDefaultAddress(address.id);
      ref.invalidate(addressesProvider);
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref, Address address) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this address?'),
        content: Text(address.singleLine),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-delete-address'),
            style: FilledButton.styleFrom(backgroundColor: AppTheme.outOfStock),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (!(confirmed ?? false)) return;

    try {
      await ref.read(shoppingRepositoryProvider).deleteAddress(address.id);
      ref.invalidate(addressesProvider);
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }
}

class _AddressCard extends StatelessWidget {
  const _AddressCard({
    required this.address,
    required this.selecting,
    required this.onSetDefault,
    required this.onDelete,
  });

  final Address address;
  final bool selecting;
  final VoidCallback onSetDefault;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: InkWell(
          key: Key('address-${address.id}'),
          borderRadius: BorderRadius.circular(14),
          onTap: selecting ? () => context.pop(address) : null,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        address.fullName,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.ink,
                        ),
                      ),
                    ),
                    if (address.isDefault)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppTheme.brand.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: const Text(
                          'DEFAULT',
                          style: TextStyle(
                            fontSize: 10,
                            letterSpacing: 0.5,
                            fontWeight: FontWeight.w800,
                            color: AppTheme.brandDark,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  address.singleLine,
                  style: const TextStyle(fontSize: 13.5, height: 1.45, color: AppTheme.muted),
                ),
                const SizedBox(height: 4),
                Text(
                  address.phone,
                  style: const TextStyle(fontSize: 13, color: AppTheme.muted),
                ),
                if ((address.deliveryInstructions ?? '').isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.info_outline_rounded, size: 14, color: AppTheme.muted),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          address.deliveryInstructions!,
                          style: const TextStyle(
                            fontSize: 12,
                            fontStyle: FontStyle.italic,
                            color: AppTheme.muted,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
                if (!selecting) ...[
                  const Divider(height: 22),
                  Row(
                    children: [
                      if (!address.isDefault)
                        TextButton(
                          key: Key('make-default-${address.id}'),
                          onPressed: onSetDefault,
                          child: const Text('Make default'),
                        ),
                      const Spacer(),
                      TextButton(
                        onPressed: () => context.push('/addresses/${address.id}/edit',
                            extra: address),
                        child: const Text('Edit'),
                      ),
                      TextButton(
                        key: Key('delete-address-${address.id}'),
                        onPressed: onDelete,
                        style: TextButton.styleFrom(foregroundColor: AppTheme.outOfStock),
                        child: const Text('Delete'),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      );
}

/// Add or edit an address. The server re-validates everything typed here.
class AddressFormScreen extends ConsumerStatefulWidget {
  const AddressFormScreen({super.key, this.existing});

  final Address? existing;

  @override
  ConsumerState<AddressFormScreen> createState() => _AddressFormScreenState();
}

class _AddressFormScreenState extends ConsumerState<AddressFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final Map<String, TextEditingController> _fields = {
    'full_name': TextEditingController(text: widget.existing?.fullName ?? ''),
    'phone': TextEditingController(text: widget.existing?.phone ?? ''),
    'house_number': TextEditingController(text: widget.existing?.houseNumber ?? ''),
    'street': TextEditingController(text: widget.existing?.street ?? ''),
    'area': TextEditingController(text: widget.existing?.area ?? ''),
    'city': TextEditingController(text: widget.existing?.city ?? ''),
    'state': TextEditingController(text: widget.existing?.state ?? ''),
    'pincode': TextEditingController(text: widget.existing?.pincode ?? ''),
    'delivery_instructions':
        TextEditingController(text: widget.existing?.deliveryInstructions ?? ''),
  };

  bool _busy = false;
  String? _formError;
  Map<String, String> _serverErrors = const {};

  bool get _isEditing => widget.existing != null;

  @override
  void dispose() {
    for (final controller in _fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _formError = null;
      _serverErrors = const {};
    });
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final payload = <String, dynamic>{
      for (final entry in _fields.entries)
        if (entry.value.text.trim().isNotEmpty) entry.key: entry.value.text.trim(),
    };

    setState(() => _busy = true);
    try {
      final repository = ref.read(shoppingRepositoryProvider);
      if (_isEditing) {
        await repository.updateAddress(widget.existing!.id, payload);
      } else {
        await repository.createAddress(payload);
      }
      ref.invalidate(addressesProvider);
      if (mounted) context.pop();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        if (error.fieldErrors.isNotEmpty) {
          _serverErrors = error.fieldErrors;
          _formKey.currentState?.validate();
        } else {
          _formError = error.message;
        }
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(_isEditing ? 'Edit address' : 'New address')),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_formError != null) ...[
                    Container(
                      key: const Key('address-form-error'),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppTheme.outOfStock.withValues(alpha: 0.07),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.outOfStock.withValues(alpha: 0.3)),
                      ),
                      child: Text(
                        _formError!,
                        style: const TextStyle(
                          color: AppTheme.outOfStock,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  _field('full_name', 'Full name', icon: Icons.person_outline_rounded),
                  _field(
                    'phone',
                    'Mobile number',
                    icon: Icons.phone_outlined,
                    keyboard: TextInputType.phone,
                    validator: _validatePhone,
                  ),
                  _field('house_number', 'Door / flat number', icon: Icons.home_outlined),
                  _field('street', 'Street'),
                  _field('area', 'Area / locality'),
                  _field('city', 'City'),
                  _field('state', 'State'),
                  _field(
                    'pincode',
                    'PIN code',
                    keyboard: TextInputType.number,
                    validator: _validatePincode,
                  ),
                  _field(
                    'delivery_instructions',
                    'Delivery instructions (optional)',
                    required: false,
                    maxLines: 2,
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    key: const Key('save-address'),
                    onPressed: _busy ? null : _submit,
                    child: _busy
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.4,
                              color: Colors.white,
                            ),
                          )
                        : Text(_isEditing ? 'Save changes' : 'Save address'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

  Widget _field(
    String name,
    String label, {
    IconData? icon,
    TextInputType? keyboard,
    bool required = true,
    int maxLines = 1,
    String? Function(String?)? validator,
  }) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: TextFormField(
          key: Key('address-$name'),
          controller: _fields[name],
          keyboardType: keyboard,
          maxLines: maxLines,
          textCapitalization:
              keyboard == null ? TextCapitalization.words : TextCapitalization.none,
          decoration: InputDecoration(
            labelText: label,
            prefixIcon: icon == null ? null : Icon(icon),
          ),
          validator: (value) {
            // A message from the server wins: it is the authority.
            if (_serverErrors[name] != null) return _serverErrors[name];
            if (validator != null) return validator(value);
            if (required && (value ?? '').trim().isEmpty) return 'This field is required.';
            return null;
          },
        ),
      );

  String? _validatePhone(String? value) {
    final text = (value ?? '').trim().replaceAll(RegExp(r'[\s-]'), '');
    if (text.isEmpty) return 'Enter a mobile number.';
    if (!RegExp(r'^(?:\+91)?[6-9]\d{9}$').hasMatch(text)) {
      return 'Enter a valid 10-digit mobile number.';
    }
    return null;
  }

  String? _validatePincode(String? value) {
    final text = (value ?? '').trim();
    if (text.isEmpty) return 'Enter a PIN code.';
    // Mirrors the server's rule and the database CHECK constraint.
    if (!RegExp(r'^[1-9][0-9]{5}$').hasMatch(text)) {
      return 'Enter a valid 6-digit PIN code.';
    }
    return null;
  }
}
