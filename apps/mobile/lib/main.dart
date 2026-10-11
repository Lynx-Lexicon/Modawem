import 'package:flutter/material.dart';

void main() {
  runApp(const ModawemApp());
}

class ModawemApp extends StatelessWidget {
  const ModawemApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Modawem',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.teal,
      ),
      home: const MainNavigationScreen(),
    );
  }
}

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    Center(child: Text('Today - اليوم', style: TextStyle(fontSize: 20))),
    Center(child: Text('Medications - الأدوية', style: TextStyle(fontSize: 20))),
    Center(child: Text('Insights - الإحصائيات', style: TextStyle(fontSize: 20))),
    Center(child: Text('History - السجل', style: TextStyle(fontSize: 20))),
    Center(child: Text('Profile - الملف الشخصي', style: TextStyle(fontSize: 20))),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color.fromARGB(255, 35, 200, 222),
        title: const Text('Modawem'),
      ),
      body: _screens[_currentIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (int index) {
          setState(() {
            _currentIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.today_outlined),
            selectedIcon: Icon(Icons.today),
            label: 'اليوم',
          ),
          NavigationDestination(
            icon: Icon(Icons.medication_outlined),
            selectedIcon: Icon(Icons.medication),
            label: 'الأدوية',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            selectedIcon: Icon(Icons.insights),
            label: 'الإحصائيات',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_outlined),
            selectedIcon: Icon(Icons.history),
            label: 'السجل',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'الملف',
          ),
        ],
      ),
    );
  }
}