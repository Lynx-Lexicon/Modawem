import 'package:material_ui/material_ui.dart';

import 'package:flutter_svg/svg.dart';

import 'package:modawem_app/core/router/routes.dart';
import 'package:modawem_app/core/theme/colors/app_tokens.dart';
import 'package:modawem_app/shared/widgets/app_text_form_field.dart';
import 'package:modawem_app/shared/widgets/logo.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() {
    return _LoginScreenState();
  }
}

class _LoginScreenState extends State<LoginScreen> {
  bool showPassword = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appTokens.surfaceSecondaryStrong,

      body: Stack(
        children: [
          Positioned.fill(
            child: SvgPicture.asset(
              "assets/images/welcome_bg_pattern.svg",
              fit: BoxFit.cover,
            ),
          ),

          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(15, 70, 15, 15),

              child: Center(
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,

                    children: [
                      const Logo(),

                      const SizedBox(height: 65),

                      AppTextFormField(
                        labelText: "البريد الإلكتروني",
                        hintText: "john.doe@example.com",
                        leading: const Icon(Icons.mail_outline_rounded),
                      ),

                      const SizedBox(height: 10),

                      AppTextFormField(
                        labelText: "كلمة المرور",
                        hintText: "كلمة المرور",
                        leading: const Icon(Icons.lock_outline_rounded),

                        trailing: Material(
                          borderRadius: BorderRadius.circular(9999),

                          child: InkWell(
                            borderRadius: BorderRadius.circular(9999),
                            onTap: () {
                              setState(() {
                                showPassword = !showPassword;
                              });
                            },

                            child: Icon(
                              showPassword
                                  ? Icons.visibility_rounded
                                  : Icons.visibility_off_rounded,
                            ),
                          ),
                        ),
                      ),

                      const SizedBox(height: 100),

                      SizedBox(
                        width: double.infinity,

                        child: FilledButton(
                          onPressed: () {
                            const SignupRoute().push(context);
                          },
                          child: Text(
                            "تسجيل الدخول",
                            style: Theme.of(context).textTheme.labelLarge!
                                .copyWith(
                                  color: context.appTokens.textPrimary,
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
