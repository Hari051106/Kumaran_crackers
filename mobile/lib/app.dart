/// The application widget: theme, router and session restore.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/config.dart';
import 'core/theme.dart';
import 'providers/providers.dart';
import 'router/app_router.dart';

class KumaranCrackersApp extends ConsumerStatefulWidget {
  const KumaranCrackersApp({super.key});

  @override
  ConsumerState<KumaranCrackersApp> createState() => _KumaranCrackersAppState();
}

class _KumaranCrackersAppState extends ConsumerState<KumaranCrackersApp> {
  late final GoRouter _router = buildRouter(
    isCheckingSession: () => ref.read(authProvider).isChecking,
  );

  @override
  void initState() {
    super.initState();
    // Restore any stored session while the splash screen is on show.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authProvider.notifier).restore();
    });
  }

  @override
  Widget build(BuildContext context) {
    // Leave the splash screen once the session check finishes - but only if
    // that is still where we are. Redirecting unconditionally would clobber a
    // deep link (a shared /product/:slug URL, or a push notification target)
    // that the app was opened with.
    ref.listen(authProvider, (previous, next) {
      final wasChecking = previous?.isChecking ?? false;
      if (!wasChecking || next.isChecking) return;

      final location = _router.routerDelegate.currentConfiguration.uri.path;
      if (location == '/') _router.go('/home');
    });

    return MaterialApp.router(
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      routerConfig: _router,
    );
  }
}
