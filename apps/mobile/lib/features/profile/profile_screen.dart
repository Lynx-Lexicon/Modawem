import 'package:material_ui/material_ui.dart';
import 'package:modawem_app/core/l10n/app_localizations_extension.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.navBarProfile)),

      body: Center(child: Text(context.l10n.navBarProfile)),
    );
  }
}
