import 'package:material_ui/material_ui.dart';

import 'package:flutter/services.dart';

import 'package:modawem_app/core/theme/colors/app_tokens.dart';

class AppTextFormField extends FormField<String> {
  AppTextFormField({
    super.key,
    super.initialValue,
    super.validator,
    super.autovalidateMode,
    super.enabled,
    super.onSaved,
    String? hintText,
    TextInputType? keyboardType,

    String? labelText,
    Widget? leading,
    Widget? trailing,
  }) : super(
         builder: (field) {
           final state = field as _AppTextFormFieldState;
           final theme = Theme.of(field.context);
           final tokens = field.context.appTokens;

           Color bgColor = tokens.surfaceWhite;
           Color mainColor = tokens.textAccentStrong;
           Color labelColor = tokens.surfaceWhite;
           if (field.hasError) {
             bgColor = tokens.surfaceDangerSubtlest;
             mainColor = tokens.textError;
             labelColor = tokens.textError;
           }

           return Column(
             spacing: 5,
             crossAxisAlignment: CrossAxisAlignment.start,

             children: [
               if (labelText != null && labelText.trim().isNotEmpty)
                 Padding(
                   padding: const EdgeInsetsDirectional.only(start: 25),
                   child: Text(
                     labelText,
                     style: theme.textTheme.labelLarge!.copyWith(
                       fontSize: 20,
                       color: labelColor,
                     ),
                   ),
                 ),

               Stack(
                 clipBehavior: Clip.none,

                 children: [
                   if (field.hasError)
                     PositionedDirectional(
                       start: 3,
                       end: 3,
                       bottom: 0,

                       child: Center(
                         child: Container(
                           padding: const EdgeInsets.only(top: 30, bottom: 5),
                           decoration: BoxDecoration(
                             color: tokens.surfaceDangerSubtlest,
                             borderRadius: const BorderRadius.vertical(
                               bottom: Radius.circular(30),
                             ),
                           ),

                           child: Column(
                             children: [
                               const SizedBox(height: 5),

                               Padding(
                                 padding: const EdgeInsetsDirectional.only(
                                   start: 15,
                                 ),
                                 child: Row(
                                   spacing: 5,
                                   crossAxisAlignment:
                                       CrossAxisAlignment.center,

                                   children: [
                                     Icon(
                                       Icons.error_rounded,
                                       color: tokens.textError,
                                       size: 20,
                                     ),
                                     Expanded(
                                       child: Text(
                                         field.errorText!,
                                         style: theme.textTheme.labelLarge!
                                             .copyWith(
                                               color: tokens.textError,
                                               fontSize: 16,
                                             ),
                                       ),
                                     ),
                                   ],
                                 ),
                               ),
                             ],
                           ),
                         ),
                       ),
                     ),

                   TapRegion(
                     groupId: EditableText,

                     child: GestureDetector(
                       behavior: HitTestBehavior.opaque,
                       onTap: enabled
                           ? () {
                               state._innerFocusNode.requestFocus();

                               if (state._innerFocusNode.hasFocus) {
                                 SystemChannels.textInput.invokeMethod(
                                   "TextInput.show",
                                 );
                               }
                             }
                           : null,
                       child: AnimatedContainer(
                         duration: const Duration(milliseconds: 300),
                         padding: const EdgeInsets.all(10),
                         margin: field.hasError
                             ? const EdgeInsets.only(bottom: 28)
                             : null,
                         decoration: BoxDecoration(
                           color: bgColor,
                           borderRadius: BorderRadius.circular(9999),
                           border: Border.all(
                             color:
                                 state._innerFocusNode.hasFocus ||
                                     field.hasError
                                 ? mainColor
                                 : Colors.transparent,
                             width: 3,
                           ),
                         ),

                         child: Stack(
                           alignment: AlignmentDirectional.centerStart,
                           clipBehavior: Clip.none,

                           children: [
                             Padding(
                               padding: EdgeInsetsDirectional.only(
                                 end: trailing != null ? 40 : 0,
                               ),
                               child: Row(
                                 spacing: 6,

                                 children: [
                                   if (leading != null) ...[
                                     IconTheme.merge(
                                       data: IconThemeData(color: mainColor),
                                       child: leading,
                                     ),

                                     SizedBox(
                                       width: 1,
                                       height: 30,

                                       child: ColoredBox(
                                         color: tokens.surfaceNeutral,
                                       ),
                                     ),
                                   ],

                                   Expanded(
                                     child: TextField(
                                       enabled: enabled,
                                       controller: state._innerController,
                                       focusNode: state._innerFocusNode,
                                       keyboardType: keyboardType,
                                       style: theme.textTheme.bodyLarge!
                                           .copyWith(fontSize: 24),
                                       decoration: InputDecoration.collapsed(
                                         hintText: hintText,
                                         hintStyle: theme.textTheme.bodyLarge!
                                             .copyWith(
                                               fontSize: 24,
                                               color: tokens.textNeutralStrong,
                                             ),
                                       ),
                                       cursorColor: mainColor,
                                       onChanged: (value) {
                                         field.didChange(value);
                                       },
                                     ),
                                   ),
                                 ],
                               ),
                             ),

                             if (trailing != null)
                               PositionedDirectional(
                                 end: 0,

                                 child: IconTheme.merge(
                                   data: IconThemeData(
                                     color: mainColor,
                                     size: 30,
                                   ),
                                   child: trailing,
                                 ),
                               ),
                           ],
                         ),
                       ),
                     ),
                   ),
                 ],
               ),
             ],
           );
         },
       );

  @override
  FormFieldState<String> createState() => _AppTextFormFieldState();
}

class _AppTextFormFieldState extends FormFieldState<String> {
  late final TextEditingController _innerController;
  late final FocusNode _innerFocusNode;

  @override
  void initState() {
    super.initState();

    _innerController = TextEditingController(text: widget.initialValue ?? '');
    _innerFocusNode = FocusNode()..addListener(_handleFocusChange);
  }

  void _handleFocusChange() => setState(() {});

  @override
  void reset() {
    _innerController.text = widget.initialValue ?? '';

    super.reset();
  }

  @override
  void dispose() {
    _innerFocusNode.removeListener(_handleFocusChange);
    _innerController.dispose();
    _innerFocusNode.dispose();

    super.dispose();
  }
}
