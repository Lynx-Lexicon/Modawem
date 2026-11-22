import 'package:material_ui/material_ui.dart';
import 'package:modawem_app/core/l10n/app_localizations.dart';

extension LocalizationsX on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this)!;
}
