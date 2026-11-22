import 'package:flutter_svg/svg.dart';
import 'package:material_ui/material_ui.dart';

enum _LogoVariant { both, image, text }

class Logo extends StatelessWidget {
  const Logo({super.key, this._flowDirection = Axis.vertical})
    : _variant = _LogoVariant.both;

  const Logo.image({super.key})
    : _flowDirection = Axis.vertical,
      _variant = _LogoVariant.image;

  const Logo.text({super.key})
    : _flowDirection = Axis.vertical,
      _variant = _LogoVariant.text;

  final Axis _flowDirection;
  final _LogoVariant _variant;

  @override
  Widget build(BuildContext context) {
    const logoImageAsset = "assets/images/modawem_logo.svg";
    const logoTextAsset = "assets/images/modawem_logo_text.svg";

    return switch (_variant) {
      _LogoVariant.image => SvgPicture.asset(logoImageAsset),
      _LogoVariant.text => SvgPicture.asset(logoTextAsset),
      _LogoVariant.both => Flex(
        direction: _flowDirection,
        spacing: 15,

        children: [
          SvgPicture.asset(logoImageAsset),
          SvgPicture.asset(logoTextAsset),
        ],
      ),
    };
  }
}
