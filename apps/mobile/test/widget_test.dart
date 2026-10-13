import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart'; // Make sure 'mobile' matches the 'name:' in your pubspec.yaml

void main() {
  testWidgets('App renders smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const MyApp());

    // Verify that the root MaterialApp widget mounts successfully.
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
