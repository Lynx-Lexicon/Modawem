import 'package:flutter/material.dart';

import 'config/app_config.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Modawem',
      home: Scaffold(
        appBar: AppBar(title: const Text('Modawem Configuration Test')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Enviroment: ${AppConfig.environment}'),
              const SizedBox(height: 20),
              Text('API URL: ${AppConfig.apiBaseUrl}'),
            ],
          ),
        ),
      ),
    );
  }
}
