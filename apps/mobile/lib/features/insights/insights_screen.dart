import 'package:material_ui/material_ui.dart';
import 'package:modawem_app/core/l10n/app_localizations_extension.dart';

class InsightsScreen extends StatelessWidget {
  const InsightsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.navBarInsights)),

      body: Center(child: Text(context.l10n.navBarInsights)),
    );
  }
}
