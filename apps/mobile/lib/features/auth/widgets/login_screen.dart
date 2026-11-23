import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import 'package:flutter_svg/svg.dart';

import 'package:modawem_app/core/theme/colors/app_tokens.dart';
import 'package:modawem_app/features/auth/auth_controller.dart';
import 'package:modawem_app/shared/widgets/app_text_form_field.dart';
import 'package:modawem_app/shared/widgets/logo.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() {
    return _LoginScreenState();
  }
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final formKey = GlobalKey<FormState>();
  bool showPassword = false;
  String email = '';
  String password = '';

  void _submit() {
    final formState = formKey.currentState!;

    if (!formState.validate()) {
      return;
    }

    formState.save();

    ref.read(authControllerProvider.notifier).login(email, password);
  }

  @override
  Widget build(BuildContext context) {
    bool isSubmitting = ref.watch(
      authControllerProvider.select((state) => state.isLoading),
    );

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
                  child: Form(
                    key: formKey,

                    child: Column(
                      mainAxisSize: MainAxisSize.min,

                      children: [
                        const Logo(),

                        const SizedBox(height: 65),

                        AppTextFormField(
                          labelText: "البريد الإلكتروني",
                          hintText: "john.doe@example.com",
                          leading: const Icon(Icons.mail_outline_rounded),
                          onSaved: (newValue) {
                            email = newValue!;
                          },
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

                          onSaved: (newValue) {
                            password = newValue!;
                          },
                        ),

                        const SizedBox(height: 100),

                        SizedBox(
                          width: double.infinity,

                          child: FilledButton(
                            onPressed: isSubmitting ? null : _submit,
                            // {
                            // const SignupRoute().push(context);
                            // },
                            child: Text(
                              isSubmitting ? "جاري التسجيل..." : "تسجيل الدخول",
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
          ),
        ],
      ),
    );
  }
}
