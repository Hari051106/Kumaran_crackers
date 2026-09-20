/// Account screen. Shows the signed-in shopper, or invites them to sign in.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../providers/providers.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final user = auth.user;

    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: user == null
          ? _SignedOut(onSignIn: () => context.push('/login'))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 27,
                          backgroundColor: AppTheme.brand.withValues(alpha: 0.12),
                          child: Text(
                            user.initials,
                            style: const TextStyle(
                              color: AppTheme.brandDark,
                              fontWeight: FontWeight.w700,
                              fontSize: 17,
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                user.fullName,
                                style: const TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.ink,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                user.email,
                                style: const TextStyle(color: AppTheme.muted, fontSize: 13),
                              ),
                              if (user.phone != null)
                                Text(
                                  user.phone!,
                                  style: const TextStyle(color: AppTheme.muted, fontSize: 13),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Named honestly rather than shown as empty, working screens.
                const _ComingSoonTile(
                  icon: Icons.receipt_long_outlined,
                  title: 'My orders',
                  subtitle: 'Arrives with the ordering release',
                ),
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Card(
                    child: ListTile(
                      key: const Key('profile-addresses'),
                      leading: const Icon(Icons.location_on_outlined, color: AppTheme.brand),
                      title: const Text(
                        'Delivery addresses',
                        style: TextStyle(fontWeight: FontWeight.w600, color: AppTheme.ink),
                      ),
                      subtitle: const Text(
                        'Where we send your orders',
                        style: TextStyle(fontSize: 12.5),
                      ),
                      trailing: const Icon(Icons.chevron_right_rounded),
                      onTap: () => context.push('/addresses'),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                OutlinedButton.icon(
                  key: const Key('logout-button'),
                  onPressed: () async {
                    await ref.read(authProvider.notifier).logout();
                    if (context.mounted) context.go('/home');
                  },
                  icon: const Icon(Icons.logout_rounded, size: 19),
                  label: const Text('Sign out'),
                ),
              ],
            ),
    );
  }
}

class _SignedOut extends StatelessWidget {
  const _SignedOut({required this.onSignIn});

  final VoidCallback onSignIn;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: AppTheme.brand.withValues(alpha: 0.10),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.person_outline_rounded,
                    size: 30, color: AppTheme.brand),
              ),
              const SizedBox(height: 18),
              const Text(
                'Sign in to your account',
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.ink,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Track your orders and check out faster. You can browse the shop '
                'without an account.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppTheme.muted, height: 1.45),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: 220,
                child: FilledButton(onPressed: onSignIn, child: const Text('Sign in')),
              ),
            ],
          ),
        ),
      );
}

class _ComingSoonTile extends StatelessWidget {
  const _ComingSoonTile({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Card(
          child: ListTile(
            leading: Icon(icon, color: AppTheme.muted),
            title: Text(
              title,
              style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.ink),
            ),
            subtitle: Text(subtitle, style: const TextStyle(fontSize: 12.5)),
            trailing: const Chip(
              label: Text('Soon', style: TextStyle(fontSize: 11)),
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
            ),
          ),
        ),
      );
}
