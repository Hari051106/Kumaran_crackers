/// Customer registration.
///
/// The role is fixed server-side as CUSTOMER; nothing sent from here can
/// influence it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_exception.dart';
import '../../core/theme.dart';
import '../../providers/providers.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();

  bool _obscure = true;
  bool _busy = false;
  String? _formError;

  /// Per-field messages returned by the server's validator.
  Map<String, String> _serverErrors = const {};

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _formError = null;
      _serverErrors = const {};
    });
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() => _busy = true);
    try {
      await ref.read(authProvider.notifier).register(
            email: _email.text.trim(),
            password: _password.text,
            fullName: _name.text.trim(),
            phone: _phone.text.trim().isEmpty ? null : _phone.text.trim(),
          );
      if (mounted) context.go('/home');
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        if (error.fieldErrors.isNotEmpty) {
          _serverErrors = error.fieldErrors;
          // Re-run validation so the server's messages appear under the fields.
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
        appBar: AppBar(title: const Text('Create account')),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'Join Kumaran Crackers',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.ink,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Create an account to place orders and follow them to your door.',
                    style: TextStyle(color: AppTheme.muted, height: 1.4),
                  ),
                  const SizedBox(height: 24),

                  if (_formError != null) ...[
                    Container(
                      key: const Key('auth-error'),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppTheme.outOfStock.withValues(alpha: 0.07),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.outOfStock.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline_rounded,
                              color: AppTheme.outOfStock, size: 20),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              _formError!,
                              style: const TextStyle(
                                color: AppTheme.outOfStock,
                                fontWeight: FontWeight.w500,
                                height: 1.35,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  TextFormField(
                    key: const Key('register-name'),
                    controller: _name,
                    textCapitalization: TextCapitalization.words,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Full name',
                      prefixIcon: Icon(Icons.person_outline_rounded),
                    ),
                    validator: (value) {
                      if (_serverErrors['full_name'] != null) return _serverErrors['full_name'];
                      final text = (value ?? '').trim();
                      if (text.length < 2) return 'Enter your full name.';
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),

                  TextFormField(
                    key: const Key('register-email'),
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Email address',
                      prefixIcon: Icon(Icons.mail_outline_rounded),
                    ),
                    validator: (value) {
                      if (_serverErrors['email'] != null) return _serverErrors['email'];
                      final text = (value ?? '').trim();
                      if (text.isEmpty) return 'Enter your email address.';
                      if (!text.contains('@') || !text.contains('.')) {
                        return 'Enter a valid email address.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),

                  TextFormField(
                    key: const Key('register-phone'),
                    controller: _phone,
                    keyboardType: TextInputType.phone,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Mobile number (optional)',
                      hintText: '9876543210',
                      prefixIcon: Icon(Icons.phone_outlined),
                    ),
                    validator: (value) {
                      if (_serverErrors['phone'] != null) return _serverErrors['phone'];
                      final text = (value ?? '').trim();
                      if (text.isEmpty) return null;
                      // Mirrors the server's rule; it remains the authority.
                      if (!RegExp(r'^(?:\+91[-\s]?|0)?[6-9]\d{9}$')
                          .hasMatch(text.replaceAll(' ', ''))) {
                        return 'Enter a valid 10-digit mobile number.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),

                  TextFormField(
                    key: const Key('register-password'),
                    controller: _password,
                    obscureText: _obscure,
                    textInputAction: TextInputAction.done,
                    onFieldSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: 'Password',
                      helperText: 'At least 8 characters, with a letter and a number.',
                      helperMaxLines: 2,
                      prefixIcon: const Icon(Icons.lock_outline_rounded),
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscure = !_obscure),
                        icon: Icon(
                          _obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                        ),
                        tooltip: _obscure ? 'Show password' : 'Hide password',
                      ),
                    ),
                    validator: (value) {
                      if (_serverErrors['password'] != null) return _serverErrors['password'];
                      final text = value ?? '';
                      if (text.length < 8) return 'Use at least 8 characters.';
                      if (!text.contains(RegExp('[A-Za-z]'))) {
                        return 'Include at least one letter.';
                      }
                      if (!text.contains(RegExp('[0-9]'))) {
                        return 'Include at least one number.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 28),

                  FilledButton(
                    key: const Key('register-submit'),
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
                        : const Text('Create account'),
                  ),
                  const SizedBox(height: 12),

                  // Fireworks are age-restricted goods. This states the rule at
                  // the point of sign-up; enforcement lives on the server.
                  const Row(
                    children: [
                      Icon(Icons.info_outline_rounded, size: 16, color: AppTheme.muted),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'You must be 18 or older to buy fireworks. Local rules on sale '
                          'and delivery apply.',
                          style: TextStyle(fontSize: 12, color: AppTheme.muted, height: 1.35),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}
