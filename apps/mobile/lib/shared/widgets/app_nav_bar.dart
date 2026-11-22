import 'package:material_ui/material_ui.dart';

import 'package:modawem_app/core/theme/colors/app_tokens.dart';

class AppNavDestinationData {
  AppNavDestinationData({
    Key? key,
    required this.icon,
    required this.activeIcon,
    required this.label,
  });

  Key? key;
  final IconData icon;
  final IconData activeIcon;
  final String label;
}

class _AppNavBarItem extends StatelessWidget {
  const _AppNavBarItem({
    super.key,
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  final IconData icon;
  final IconData activeIcon;
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: AspectRatio(
        aspectRatio: 1 / 1,

        child: InkWell(
          onTap: onTap,
          child: Container(
            clipBehavior: Clip.hardEdge,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(9999),
              color: isActive
                  ? context.appTokens.surfaceWhite
                  : Colors.transparent,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,

              children: [Icon(isActive ? activeIcon : icon), Text(label)],
            ),
          ),
        ),
      ),
    );
  }
}

class AppNavBar extends StatelessWidget {
  const AppNavBar({
    super.key,
    required this.destinations,
    required this.selectedDestination,
    required this.onSelectDestination,
  });

  final List<AppNavDestinationData> destinations;
  final int selectedDestination;
  final ValueChanged<int> onSelectDestination;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        decoration: BoxDecoration(color: context.appTokens.surfaceNeutral),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 10),
          child: Center(
            heightFactor: 1,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 350),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,

                children: destinations.indexed.map((dest) {
                  final (i, d) = dest;

                  return _AppNavBarItem(
                    key: d.key,
                    icon: d.icon,
                    activeIcon: d.activeIcon,
                    label: d.label,
                    isActive: selectedDestination == i,
                    onTap: () {
                      onSelectDestination(i);
                    },
                  );
                }).toList(),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
