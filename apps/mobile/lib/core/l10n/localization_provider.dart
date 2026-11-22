import 'package:material_ui/material_ui.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

class LocalizationNotifier extends Notifier<Locale> {
  @override
  build() {
    return const Locale("ar");
  }

  void switchLocale(Locale locale) {
    state = locale;
  }
}

final localizationProvider = NotifierProvider<LocalizationNotifier, Locale>(
  () => LocalizationNotifier(),
);
