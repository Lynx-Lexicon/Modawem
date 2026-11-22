// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Modawem';

  @override
  String get titleLogin => 'Log In';

  @override
  String get navBarHome => 'Overview';

  @override
  String get navBarMedications => 'Medications';

  @override
  String get navBarInsights => 'Insights';

  @override
  String get navBarHistory => 'History';

  @override
  String get navBarProfile => 'Profile';
}
