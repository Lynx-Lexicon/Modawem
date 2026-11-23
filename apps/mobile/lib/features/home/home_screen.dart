import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';
import 'package:modawem_app/core/l10n/app_localizations_extension.dart';
import 'package:modawem_app/features/auth/auth_controller.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.navBarHome)),

      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(context.l10n.navBarHome),
            Text("Hello ${ref.read(authControllerProvider).value!.firstName}"),
          ],
        ),
      ),
    );
  }
}
