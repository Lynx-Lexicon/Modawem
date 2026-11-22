import 'package:material_ui/material_ui.dart';
import 'package:modawem_app/core/l10n/app_localizations_extension.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.navBarHistory)),

      body: Center(child: Text(context.l10n.navBarHistory)),
    );
  }
}
