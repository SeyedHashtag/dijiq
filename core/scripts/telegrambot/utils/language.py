from telebot import types
from utils.command import bot

LANGUAGES = {
    "🇺🇸 English": "en",
    "🇸🇦 العربية": "ar",
    "🇮🇷 فارسی": "fa",
    "🇪🇸 Español": "es",
    "🇧🇷 Português": "pt",
    "🇮🇳 हिंदी": "hi",
    "🇹🇲 Türkmençe": "tk",
    "🇨🇳 中文": "zh",
    "🇷🇺 Русский": "ru"
}

# Store user language preferences (in-memory for now, consider using database)
user_languages = {}

def get_language_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(*[types.KeyboardButton(lang) for lang in LANGUAGES.keys()])
    return markup

def get_user_language(user_id):
    return user_languages.get(user_id, "en")

def set_user_language(user_id, language):
    user_languages[user_id] = LANGUAGES.get(language, "en")

# Translation dictionary - expand this with more translations
TRANSLATIONS = {
    "en": {
        "select_language": "Please select your language:",
        "language_selected": "Language set to English",
        "view_configs": "🔑 My Configs",
        "view_plans": "📦 Plans",
        "downloads": "⬇️ Downloads",
        "support": "❓ Support/Help",
        "welcome_client": "Welcome to our VPN service! Please select an option:",
        "basic_plan": "🚀 Basic Plan",
        "premium_plan": "⚡️ Premium Plan",
        "ultimate_plan": "💎 Ultimate Plan",
        "plan_details": """*{name}*
• {traffic}GB Traffic
• {days} Days
• Price: ${price}""",
        "select_plan": "Please select a plan:",
        "back_to_menu": "↩️ Back to Menu",
        "payment_settings": "💳 Payment Settings",
        "current_payment_settings": """*Current Payment Settings*

Merchant ID: `{merchant_id}`
API Key: `{api_key}`
Currency: {currency}
Network: {network}

Status: {status}""",
        "payment_settings_menu": "Select what you want to configure:",
        "set_merchant": "Set Merchant ID",
        "set_api_key": "Set API Key",
        "set_currency": "Set Currency",
        "set_network": "Set Network",
        "test_payment": "Test Payment System",
        "enter_merchant_id": "Please enter the Merchant ID:",
        "enter_api_key": "Please enter the API Key:",
        "enter_currency": "Please enter the currency (e.g., USDT):",
        "enter_network": "Please enter the network (e.g., tron):",
        "settings_updated": "✅ Settings updated successfully!",
        "test_success": "✅ Payment system is working correctly!",
        "test_failed": "❌ Payment system test failed: {error}",
        "select_platform": "Select your platform:",
        "android_store": "📱 Android (Play Store)",
        "android_direct": "📱 Android (Direct APK)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 Windows",
        "other_platforms": "🌐 Other Platforms",
        "download_title": "📶 Download Hiddify",
        "download_links": """*Available Download Links:*

📱 *Android:*
• [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [Direct APK](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [App Store](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *Windows:*
• [Download Setup](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *Other Platforms:*
• [GitHub Releases](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ Warning: You are sending messages too quickly. ({current}/{limit} messages)",
        "spam_blocked": "🚫 You have been blocked for {duration} seconds for spam.",
        "spam_wait": "You are temporarily blocked for spam. Please wait {time} seconds.",
        "test_mode_config": "🧪 Test mode: Creating your configuration...",
        "payment_link_exists": "You already have an active payment link for this plan. Please wait {minutes} minutes before requesting a new one, or complete/cancel the existing payment.",
        "check_payment": "Check Payment Status",
        "payment_success": "💰 Payment successful! Creating your configuration...",
        "payment_failed": "❌ Payment failed or expired. Please try again.",
        "config_error": "Error creating configuration: {error}",
        "uri_error": "Error getting URIs: {error}",
        "config_created": "Configuration created successfully!",
        "your_config": """*Your VPN Configuration*

🔗 *Direct URI:*
`{direct_uri}`

📱 *SingBox Subscription:*
`{singbox_sub}`

🌐 *Normal Subscription:*
`{normal_sub}`

📊 *Plan Details:*
• Traffic: {traffic}GB
• Duration: {days} days
• Created: {created_at}""",
        "qr_caption": "QR Code for {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "ar": {
        "select_language": "يرجى اختيار لغتك:",
        "language_selected": "تم تعيين اللغة إلى العربية",
        "view_configs": "🔑 تكويناتي",
        "view_plans": "📦 الخطط",
        "downloads": "⬇️ التنزيلات",
        "support": "❓ الدعم/المساعدة",
        "welcome_client": "مرحبًا بك في خدمة VPN الخاصة بنا! يرجى تحديد خيار:",
        "basic_plan": "🚀 الخطة الأساسية",
        "premium_plan": "⚡️ الخطة المميزة",
        "ultimate_plan": "💎 الخطة المطلقة",
        "plan_details": """*{name}*
• {traffic} جيجابايت حركة مرور
• {days} يوم
• السعر: ${price}""",
        "select_plan": "يرجى اختيار خطة:",
        "back_to_menu": "↩️ العودة إلى القائمة",
        "payment_settings": "💳 إعدادات الدفع",
        "current_payment_settings": """*إعدادات الدفع الحالية*

معرف التاجر: `{merchant_id}`
مفتاح API: `{api_key}`
العملة: {currency}
الشبكة: {network}

الحالة: {status}""",
        "payment_settings_menu": "��ختر ما تريد تكوينه:",
        "set_merchant": "تعيين معرف التاجر",
        "set_api_key": "تعيين مفتاح API",
        "set_currency": "تعيين العملة",
        "set_network": "تعيين الشبكة",
        "test_payment": "اختبار نظام الدفع",
        "enter_merchant_id": "يرجى إدخال معرف التاجر:",
        "enter_api_key": "يرجى إدخال مفتاح API:",
        "enter_currency": "يرجى إدخال العملة (مثل USDT):",
        "enter_network": "يرجى إدخال الشبكة (مثل Tron):",
        "settings_updated": "✅ تم تحديث الإعدادات بنجاح!",
        "test_success": "✅ يعمل نظام الدفع بشكل صحيح!",
        "test_failed": "❌ فشل اختبار نظام الدفع: {error}",
        "select_platform": "اختر منصتك:",
        "android_store": "📱 أندرويد (متجر Play)",
        "android_direct": "📱 أندرويد (APK مباشر)",
        "ios": "📱 iOS (متجر التطبيقات)",
        "windows": "💻 ويندوز",
        "other_platforms": "🌐 منصات أخرى",
        "download_title": "📶 تحميل Hiddify",
        "download_links": """*روابط التنزيل المتاحة:*

📱 *أندرويد:*
• [متجر Play](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [APK مباشر](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [متجر التطبيقات](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *ويندوز:*
• [تحميل الإعداد](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *منصات أخرى:*
• [إصدارات GitHub](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ تحذير: أنت ترسل الرسائل بسرعة كبيرة. ({current}/{limit} رسائل)",
        "spam_blocked": "🚫 لقد تم حظرك لمدة {duration} ثانية بسبب الرسائل المزعجة.",
        "spam_wait": "لقد تم حظر حسابك مؤقتًا بسبب الرسائل المزعجة. يرجى الانتظار {time} ثانية.",
        "test_mode_config": "🧪 وضع الاختبار: جاري إنشاء تكوينك...",
        "payment_link_exists": "لديك بالفعل رابط دفع نشط لهذه الخطة. يرجى الانتظار {minutes} دقيقة قبل طلب رابط جديد، أو إكمال/إلغاء الدفع الحالي.",
        "check_payment": "تحقق من حالة الدفع",
        "payment_success": "💰 تم الدفع بنجاح! جاري إنشاء تكوينك...",
        "payment_failed": "❌ فشل الدفع أو انتهت صلاحيته. يرجى المحاولة مرة أخرى.",
        "config_error": "خطأ في إنشاء التكوين: {error}",
        "uri_error": "خطأ في الحصول على URI: {error}",
        "config_created": "تم إنشاء التكوين بنجاح!",
        "your_config": """*تكوين VPN الخاص بك*

🔗 *URI مباشر:*
`{direct_uri}`

📱 *اشتراك SingBox:*
`{singbox_sub}`

🌐 *اشتراك Normal:*
`{normal_sub}`

📊 *تفاصيل الخطة:*
• حركة مرور: {traffic} جيجابايت
• المدة: {days} يوم
• تم الإنشاء: {created_at}""",
        "qr_caption": "رمز QR لـ {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "fa": {
        "select_language": "لطفاً زبان خود را انتخاب کنید:",
        "language_selected": "زبان به فارسی تنظیم شد",
        "view_configs": "🔑 پیکربندی‌های من",
        "view_plans": "📦 طرح‌ها",
        "downloads": "⬇️ دانلودها",
        "support": "❓ پشتیبانی/کمک",
        "welcome_client": "به سرویس VPN ما خوش آمدید! لطفاً یک گزینه را انتخاب کنید:",
        "basic_plan": "🚀 طرح پایه",
        "premium_plan": "⚡️ طرح پریمیوم",
        "ultimate_plan": "💎 طرح نهایی",
        "plan_details": """*{name}*
• {traffic} گیگابایت ترافیک
• {days} روز
• قیمت: ${price}""",
        "select_plan": "لطفاً یک طرح را انتخاب کنید:",
        "back_to_menu": "↩️ بازگشت به منو",
        "payment_settings": "💳 تنظیمات پرداخت",
        "current_payment_settings": """*تنظیمات پرداخت فعلی*

شناسه فروشنده: `{merchant_id}`
کلید API: `{api_key}`
ارز: {currency}
شبکه: {network}

وضعیت: {status}""",
        "payment_settings_menu": "��نتخاب کنید چه چیزی را می‌خواهید تنظیم کنید:",
        "set_merchant": "تنظیم شناسه فروشنده",
        "set_api_key": "تنظیم کلید API",
        "set_currency": "تنظیم ارز",
        "set_network": "تنظیم شبکه",
        "test_payment": "تست سیستم پرداخت",
        "enter_merchant_id": "لطفاً شناسه فروشنده را وارد کنید:",
        "enter_api_key": "لطفاً کلید API را وارد کنید:",
        "enter_currency": "لطفاً ارز را وارد کنید (مثلاً USDT):",
        "enter_network": "لطفاً شبکه را وارد کنید (مثلاً tron):",
        "settings_updated": "✅ تنظیمات با موفقیت به‌روزرسانی شد!",
        "test_success": "✅ سیستم پرداخت به درستی کار می‌کند!",
        "test_failed": "❌ تست سیستم پرداخت ناموفق بود: {error}",
        "select_platform": "پلتفرم خود را انتخاب کنید:",
        "android_store": "📱 اندروید (Play Store)",
        "android_direct": "📱 اندروید (APK مستقیم)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 ویندوز",
        "other_platforms": "🌐 پلتفرم‌های دیگر",
        "download_title": "📶 دانلود Hiddify",
        "download_links": """*لینک‌های دانلود موجود:*

📱 *اندروید:*
• [متجر Play](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [APK مستقیم](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [متجر التطبيقات](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *ویندوز:*
• [دانلود نصب](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *پلتفرم‌های دیگر:*
• [انتشارات GitHub](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ هشدار: شما پیام‌ها را خیلی سریع می‌فرستید. ({current}/{limit} پیام)",
        "spam_blocked": "🚫 به مدت {duration} ثانیه به دلیل ارسال پیام‌های ناخواسته مسدود شدید.",
        "spam_wait": "حساب شما به طور موقت به دلیل ارسال پیام‌های ناخواسته مسدود شده است. لطفاً {time} ثانیه صبر کنید.",
        "test_mode_config": "🧪 حالت تست: در حال ایجاد پیکربندی شما...",
        "payment_link_exists": "شما بالفعل یک لینک پرداخت فعال برای این طرح دارید. لطفاً {minutes} دقیقه صبر کنید قبل از درخواست لینک جدید، یا پرداخت فعلی را تکمیل/لغو کنید.",
        "check_payment": "بررسی وضعیت پرداخت",
        "payment_success": "💰 تم الدفع بنجاح! جاري إنشاء تكوينك...",
        "payment_failed": "❌ فشل الدفع أو انتهت صلاحيته. يرجى المحاولة مرة أخرى.",
        "config_error": "خطا در ایجاد پیکربندی: {error}",
        "uri_error": "خطا در دریافت URI: {error}",
        "config_created": "پیکربندی با موفقیت ایجاد شد!",
        "your_config": """*پیکربندی VPN شما*

🔗 *URI مستقیم:*
`{direct_uri}`

📱 *اشتراک SingBox:*
`{singbox_sub}`

🌐 *اشتراک Normal:*
`{normal_sub}`

📊 *جزئیات طرح:*
• ترافیک: {traffic} گیگابایت
• مدت زمان: {days} روز
• ایجاد شده در: {created_at}""",
        "qr_caption": "کد QR برای {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "es": {
        "select_language": "Por favor, selecciona tu idioma:",
        "language_selected": "Idioma configurado a Español",
        "view_configs": "🔑 Mis Configuraciones",
        "view_plans": "📦 Planes",
        "downloads": "⬇️ Descargas",
        "support": "❓ Soporte/Ayuda",
        "welcome_client": "¡Bienvenido a nuestro servicio VPN! Por favor, selecciona una opción:",
        "basic_plan": "🚀 Plan Básico",
        "premium_plan": "⚡️ Plan Premium",
        "ultimate_plan": "💎 Plan Ultimate",
        "plan_details": """*{name}*
• {traffic}GB de Tráfico
• {days} Días
• Precio: ${price}""",
        "select_plan": "Por favor, selecciona un plan:",
        "back_to_menu": "↩️ Volver al Menú",
        "payment_settings": "💳 Configuración de Pagos",
        "current_payment_settings": """*Configuración de Pagos Actual*

ID de Comerciante: `{merchant_id}`
Clave API: `{api_key}`
Moneda: {currency}
Red: {network}

Estado: {status}""",
        "payment_settings_menu": "Selecciona lo que deseas configurar:",
        "set_merchant": "Establecer ID de Comerciante",
        "set_api_key": "Establecer Clave API",
        "set_currency": "Establecer Moneda",
        "set_network": "Establecer Red",
        "test_payment": "Probar Sistema de Pagos",
        "enter_merchant_id": "Por favor, ingresa el ID de Comerciante:",
        "enter_api_key": "Por favor, ingresa la Clave API:",
        "enter_currency": "Por favor, ingresa la moneda (ej., USDT):",
        "enter_network": "Por favor, ingresa la red (ej., tron):",
        "settings_updated": "✅ ¡Configuraciones actualizadas exitosamente!",
        "test_success": "✅ ¡El sistema de pagos funciona correctamente!",
        "test_failed": "❌ La prueba del sistema de pagos falló: {error}",
        "select_platform": "Selecciona tu plataforma:",
        "android_store": "📱 Android (Play Store)",
        "android_direct": "📱 Android (APK Directo)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 Windows",
        "other_platforms": "🌐 Otras Plataformas",
        "download_title": "📶 Descargar Hiddify",
        "download_links": """*Enlaces de Descarga Disponibles:*

📱 *Android:*
• [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [APK Directo](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [App Store](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *Windows:*
• [Descargar Instalador](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *Otras Plataformas:*
• [Lanzamientos de GitHub](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ Advertencia: Estás enviando mensajes demasiado rápido. ({current}/{limit} mensajes)",
        "spam_blocked": "🚫 Has sido bloqueado por {duration} segundos por spam.",
        "spam_wait": "Estás temporalmente bloqueado por spam. Por favor, espera {time} segundos.",
        "test_mode_config": "🧪 Modo de prueba: Creando tu configuración...",
        "payment_link_exists": "Ya tienes un enlace de pago activo para este plan. Por favor, espera {minutes} minutos antes de solicitar uno nuevo, o completa/cancela el pago existente.",
        "check_payment": "Verificar Estado del Pago",
        "payment_success": "💰 ¡Pago exitoso! Creando tu configuración...",
        "payment_failed": "❌ El pago falló o expiró. Por favor, inténtalo de nuevo.",
        "config_error": "Error al crear la configuración: {error}",
        "uri_error": "Error al obtener el URI: {error}",
        "config_created": "¡Configuración creada exitosamente!",
        "your_config": """*Tu Configuración VPN*

🔗 *URI Directo:*
`{direct_uri}`

📱 *Suscripción SingBox:*
`{singbox_sub}`

🌐 *Suscripción Normal:*
`{normal_sub}`

📊 *Detalles del Plan:*
• Tráfico: {traffic}GB
• Duración: {days} días
• Creado en: {created_at}""",
        "qr_caption": "Código QR para {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "pt": {
        "select_language": "Por favor, selecione seu idioma:",
        "language_selected": "Idioma definido para Português",
        "view_configs": "🔑 Minhas Configurações",
        "view_plans": "📦 Planos",
        "downloads": "⬇️ Downloads",
        "support": "❓ Suporte/Ajuda",
        "welcome_client": "Bem-vindo ao nosso serviço VPN! Por favor, selecione uma opção:",
        "basic_plan": "🚀 Plano Básico",
        "premium_plan": "⚡️ Plano Premium",
        "ultimate_plan": "💎 Plano Ultimate",
        "plan_details": """*{name}*
• {traffic}GB de Tráfego
• {days} Dias
• Preço: ${price}""",
        "select_plan": "Por favor, selecione um plano:",
        "back_to_menu": "↩️ Voltar ao Menu",
        "payment_settings": "💳 Configurações de Pagamento",
        "current_payment_settings": """*Configurações de Pagamento Atuais*

ID do Comerciante: `{merchant_id}`
Chave API: `{api_key}`
Moeda: {currency}
Rede: {network}

Status: {status}""",
        "payment_settings_menu": "Selecione o que deseja configurar:",
        "set_merchant": "Definir ID do Comerciante",
        "set_api_key": "Definir Chave API",
        "set_currency": "Definir Moeda",
        "set_network": "Definir Rede",
        "test_payment": "Testar Sistema de Pagamento",
        "enter_merchant_id": "Por favor, insira o ID do Comerciante:",
        "enter_api_key": "Por favor, insira a Chave API:",
        "enter_currency": "Por favor, insira a moeda (ex., USDT):",
        "enter_network": "Por favor, insira a rede (ex., tron):",
        "settings_updated": "✅ Configurações atualizadas com sucesso!",
        "test_success": "✅ O sistema de pagamento está funcionando corretamente!",
        "test_failed": "❌ O teste do sistema de pagamento falhou: {error}",
        "select_platform": "Selecione sua plataforma:",
        "android_store": "📱 Android (Play Store)",
        "android_direct": "📱 Android (APK Direto)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 Windows",
        "other_platforms": "🌐 Outras Plataformas",
        "download_title": "📶 Baixar Hiddify",
        "download_links": """*Links de Download Disponíveis:*

📱 *Android:*
• [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [APK Direto](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [App Store](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *Windows:*
• [Baixar Instalador](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *Outras Plataformas:*
• [Lançamentos no GitHub](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ Aviso: Você está enviando mensagens muito rapidamente. ({current}/{limit} mensagens)",
        "spam_blocked": "🚫 Você foi bloqueado por {duration} segundos por spam.",
        "spam_wait": "Você está temporariamente bloqueado por spam. Por favor, espere {time} segundos.",
        "test_mode_config": "🧪 Modo de teste: Criando sua configuração...",
        "payment_link_exists": "Você já tem um link de pagamento ativo para este plano. Por favor, espere {minutes} minutos antes de solicitar um novo, ou complete/cancele o pagamento existente.",
        "check_payment": "Verificar Status do Pagamento",
        "payment_success": "💰 Pagamento bem-sucedido! Criando sua configuração...",
        "payment_failed": "❌ Pagamento falhou ou expirou. Por favor, tente novamente.",
        "config_error": "Erro ao criar a configuração: {error}",
        "uri_error": "Erro ao obter o URI: {error}",
        "config_created": "Configuração criada com sucesso!",
        "your_config": """*Sua Configuração VPN*

🔗 *URI Direto:*
`{direct_uri}`

📱 *Assinatura SingBox:*
`{singbox_sub}`

🌐 *Assinatura Normal:*
`{normal_sub}`

📊 *Detalhes do Plano:*
• Tráfego: {traffic}GB
• Duração: {days} dias
• Criado em: {created_at}""",
        "qr_caption": "Código QR para {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "hi": {
        "select_language": "कृपया अपनी भाषा चुनें:",
        "language_selected": "भाषा हिंदी में सेट हो गई है",
        "view_configs": "🔑 मेरी कॉन्फ़िगरेशन",
        "view_plans": "📦 योजनाएँ",
        "downloads": "⬇️ डाउनलोड्स",
        "support": "❓ समर्थन/सहायता",
        "welcome_client": "हमारी VPN सेवा में आपका स्वागत है! कृपया एक विकल्प चुनें:",
        "basic_plan": "🚀 बेसिक प्लान",
        "premium_plan": "⚡️ प्रीमियम प्लान",
        "ultimate_plan": "💎 अल्टीमेट प्लान",
        "plan_details": """*{name}*
• {traffic}GB ट्रैफ़िक
• {days} दिन
• कीमत: ${price}""",
        "select_plan": "कृपया एक योजना चुनें:",
        "back_to_menu": "↩️ मेनू पर वापस",
        "payment_settings": "💳 भुगतान सेटिंग्स",
        "current_payment_settings": """*वर्तमान भुगतान सेटिंग्स*

व्यापारी आईडी: `{merchant_id}`
API कुंजी: `{api_key}`
मुद्रा: {currency}
नेटवर्क: {network}

स्थिति: {status}""",
        "payment_settings_menu": "चुनें कि आप क्या कॉन्फ़िगर करना चाहते हैं:",
        "set_merchant": "व्यापारी आईडी सेट करें",
        "set_api_key": "API कुंजी सेट करें",
        "set_currency": "मुद्रा सेट करें",
        "set_network": "नेटवर्क सेट करें",
        "test_payment": "भुगतान प्रणाली का परीक्षण करें",
        "enter_merchant_id": "कृपया व्यापारी आईडी दर्ज करें:",
        "enter_api_key": "कृपया API कुंजी दर्ज करें:",
        "enter_currency": "कृपया मुद्रा दर्ज करें (जैसे, USDT):",
        "enter_network": "कृपया नेटवर्क दर्ज करें (जैसे, ट्रॉन):",
        "settings_updated": "✅ सेटिंग्स सफलत���पूर्वक अपडेट हो गई हैं!",
        "test_success": "✅ भुगतान प्रणाली सही से काम कर रही है!",
        "test_failed": "❌ भुगतान प्रणाली का परीक्षण विफल रहा: {error}",
        "select_platform": "अपना प्लेटफ़ॉर्म चुनें:",
        "android_store": "📱 एंड्रॉइड (प्लेस्टोर)",
        "android_direct": "📱 एंड्रॉइड (डायरेक्ट APK)",
        "ios": "📱 iOS (एप स्टोर)",
        "windows": "💻 विंडोज़",
        "other_platforms": "🌐 अन्य प्लेटफ़ॉर्म",
        "download_title": "📶 Hiddify डाउनलोड करें",
        "download_links": """*उपलब्ध डाउनलोड लिंक:*

📱 *एंड्रॉइड:*
• [प्लेस्टोर](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [डायरेक्ट APK](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [एप स्टोर](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *विं���ोज़:*
• [इंस्टॉलर डाउनलोड करें](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *अन्य प्लेटफ़ॉर्म:*
• [GitHub रिलीज़](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ चेतावनी: आप बहुत जल्दी संदेश भेज रहे हैं। ({current}/{limit} संदेश)",
        "spam_blocked": "🚫 आपको स्पैम के लिए {duration} सेकंड के लिए ब्लॉक कर दिया गया है।",
        "spam_wait": "आप अस्थायी रूप से स्पैम के लिए ब्लॉक हैं। कृपया {time} सेकंड प्रतीक्षा करें।",
        "test_mode_config": "🧪 परीक्षण मोड: आपकी कॉन्फ़िगरेशन बना रहा है...",
        "payment_link_exists": "आपके पास पहले से ही इस योजना के लिए एक सक्रिय भुगतान लिंक है। कृपया नया लिंक अनुरोध करने से पहले {minutes} मि��ट प्रतीक्षा करें, या मौजूदा भुगतान पूरा/रद्द करें।",
        "check_payment": "भुगतान स्थिति जांचें",
        "payment_success": "💰 भुगतान सफल! आपकी कॉन्फ़िगरेशन बना रहा है...",
        "payment_failed": "❌ भुगतान विफल या समाप्त हो गया। कृपया पुनः प्रयास करें।",
        "config_error": "कॉन्फ़िगरेशन बनाने में त्रुटि: {error}",
        "uri_error": "URI प्राप्त करने में त्रुटि: {error}",
        "config_created": "कॉन्फ़िगरेशन सफलतापूर्वक बना लिया गया है!",
        "your_config": """*आपकी VPN कॉन्फ़िगरेशन*

🔗 *प्रत्यक्ष URI:*
`{direct_uri}`

📱 *SingBox सदस्यता:*
`{singbox_sub}`

🌐 *Normal सदस्यता:*
`{normal_sub}`

📊 *योजना विवरण:*
• ट्रैफ़िक: {traffic}GB
• अवधि: {days} दिन
• बनाया गया: {created_at}""",
        "qr_caption": "{username} के लिए QR कोड",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "tk": {
        "select_language": "Zňada, dilini saýlaň:",
        "language_selected": "Dil türkmençä saýlandy",
        "view_configs": "🔑 Meniň Konfigurasiýalarym",
        "view_plans": "📦 Planlar",
        "downloads": "⬇️ Ýüklemeler",
        "support": "❓ Goldaw/Yardam",
        "welcome_client": "VPN hyzmatymyza hoş geldiňiz! Zňada bir opsiýany saýlaň:",
        "basic_plan": "🚀 Esasy Plan",
        "premium_plan": "⚡️ Premium Plan",
        "ultimate_plan": "💎 Ähli Täjribeli Plan",
        "plan_details": """*{name}*
• {traffic}GB Trafik
• {days} Gün
• Bahasy: ${price}""",
        "select_plan": "Zňada bir plan saýlaň:",
        "back_to_menu": "↩️ Menüdega gaýt",
        "payment_settings": "💳 Töleg Beýannamalary",
        "current_payment_settings": """*Häzirki Töleg Beýannamalary*

Tijaretçiler IDsi: `{merchant_id}`
API açary: `{api_key}`
Pul birligi: {currency}
Törän: {network}

Status: {status}""",
        "payment_settings_menu": "Haýyş edýän, näme sazlamalygyz saýlaň:",
        "set_merchant": "Tijaretçiler IDsi sazlaň",
        "set_api_key": "API açaryny sazlaň",
        "set_currency": "Pul birligini sazlaň",
        "set_network": "Torni sazlaň",
        "test_payment": "Töleg ulgamy synaň",
        "enter_merchant_id": "Tijaretçiler IDsi giriziň:",
        "enter_api_key": "API açaryny giriziň:",
        "enter_currency": "Pul birligini giriziň (meselem, USDT):",
        "enter_network": "Torni giriziň (meselem, tron):",
        "settings_updated": "✅ Beýannamalary üstünlikli täzelendi!",
        "test_success": "✅ Töleg ulgamy dogry işleýär!",
        "test_failed": "❌ Töleg ulgamy synawy başarnyksyz boldy: {error}",
        "select_platform": "Platforma saýlaň:",
        "android_store": "📱 Android (Play Store)",
        "android_direct": "📱 Android (Direkt APK)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 Windows",
        "other_platforms": "🌐 Outras Plataformas",
        "download_title": "📶 Descargar Hiddify",
        "download_links": """*Enlaces de Descarga Disponibles:*

📱 *Android:*
• [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [APK Directo](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [App Store](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *Windows:*
• [Descargar Instalador](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *Outras Plataformas:*
• [Lançamentos no GitHub](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ Advertencia: Estás enviando mensajes demasiado rápido. ({current}/{limit} mensajes)",
        "spam_blocked": "🚫 Has sido bloqueado por {duration} segundos por spam.",
        "spam_wait": "Estás temporalmente bloqueado por spam. Por favor, espera {time} segundos.",
        "test_mode_config": "🧪 Modo de prueba: Creando tu configuración...",
        "payment_link_exists": "Ya tienes un enlace de pago activo para este plan. Por favor, espera {minutes} minutos antes de solicitar uno nuevo, o completa/cancela el pago existente.",
        "check_payment": "Verificar Estado del Pago",
        "payment_success": "💰 ¡Pago exitoso! Creando tu configuración...",
        "payment_failed": "❌ El pago falló o expiró. Por favor, inténtalo de nuevo.",
        "config_error": "Error al crear la configuración: {error}",
        "uri_error": "Error al obtener el URI: {error}",
        "config_created": "¡Configuración creada exitosamente!",
        "your_config": """*Tu Configuración VPN*

🔗 *URI Directo:*
`{direct_uri}`

📱 *Suscripción SingBox:*
`{singbox_sub}`

🌐 *Suscripción Normal:*
`{normal_sub}`

📊 *Detalles del Plan:*
• Tráfico: {traffic}GB
• Duración: {days} días
• Creado en: {created_at}""",
        "qr_caption": "Código QR para {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "zh": {
        "select_language": "请选择您的语言：",
        "language_selected": "语言已设置为中文",
        "view_configs": "🔑 我的配置",
        "view_plans": "📦 计划",
        "downloads": "⬇️ 下载",
        "support": "❓ 支持/帮助",
        "welcome_client": "欢迎使用我们的VPN服务！请选择一个选项：",
        "basic_plan": "🚀 基本计划",
        "premium_plan": "⚡️ 高级计划",
        "ultimate_plan": "💎 终极计划",
        "plan_details": """*{name}*
• {traffic}GB 流量
• {days} 天
• 价格: ${price}""",
        "select_plan": "请选择一个计划：",
        "back_to_menu": "↩️ 返回菜单",
        "payment_settings": "💳 支付设置",
        "current_payment_settings": """*当前支付设置*

商户 ID: `{merchant_id}`
API 密钥: `{api_key}`
货币: {currency}
网络: {network}

状态: {status}""",
        "payment_settings_menu": "选择您要配置的内容：",
        "set_merchant": "设置商户 ID",
        "set_api_key": "设置 API 密钥",
        "set_currency": "设置货币",
        "set_network": "设置网络",
        "test_payment": "测试支付系统",
        "enter_merchant_id": "请输入商户 ID：",
        "enter_api_key": "请输入 API 密钥：",
        "enter_currency": "请输入货币（例如 USDT）：",
        "enter_network": "请输入网络（例如 tron）：",
        "settings_updated": "✅ 设置已成功更新！",
        "test_success": "✅ 支付系统运行正常！",
        "test_failed": "❌ 支付系统测试失败：{error}",
        "select_platform": "选择您的平台：",
        "android_store": "📱 Android (Play Store)",
        "android_direct": "📱 Android (直接 APK)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 Windows",
        "other_platforms": "🌐 其他平台",
        "download_title": "📶 下载 Hiddify",
        "download_links": """*可用的下载链接：*

📱 *Android:*
• [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [直接 APK](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [App Store](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *Windows:*
• [下载安装程序](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *其他平台:*
• [GitHub 发布](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ 警告：您发送消息的速度太快了。({current}/{limit} 条消息)",
        "spam_blocked": "🚫 您已被禁止发送垃圾信息 {duration} 秒。",
        "spam_wait": "您的账户因发送垃圾信息而被暂时禁止。请等待 {time} 秒。",
        "test_mode_config": "🧪 测试模式：正在创建您的配置...",
        "payment_link_exists": "您已经有一个活动的支付链接用于此计划。请等待 {minutes} 分钟，然后再请求新的链接，或完成/取消现有支付。",
        "check_payment": "检查支付状态",
        "payment_success": "💰 支付成功！正在创建您的配置...",
        "payment_failed": "❌ 支付失败或已过期。请再试一次。",
        "config_error": "配置错误：{error}",
        "uri_error": "获取 URI 错误：{error}",
        "config_created": "配置已成功创建！",
        "your_config": """*您的 VPN 配置*

🔗 *直接 URI:*
`{direct_uri}`

📱 *SingBox 订阅:*
`{singbox_sub}`

🌐 *普通订阅:*
`{normal_sub}`

📊 *计划详情:*
• 流量: {traffic}GB
• 持续时间: {days} 天
• 创建于: {created_at}""",
        "qr_caption": "{username} 的二维码",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    },
    "ru": {
        "select_language": "Пожалуйста, выберите ваш язык:",
        "language_selected": "Язык установлен на русский",
        "view_configs": "🔑 Мои конфигурации",
        "view_plans": "📦 Планы",
        "downloads": "⬇️ Скачивания",
        "support": "❓ Поддержка/Помощь",
        "welcome_client": "Добро пожаловать в наш VPN сервис! Пожалуйста, выберите опцию:",
        "basic_plan": "🚀 Базовый план",
        "premium_plan": "⚡️ Премиум план",
        "ultimate_plan": "💎 Ультра план",
        "plan_details": """*{name}*
• {traffic}GB Трафик
• {days} Дней
• Цена: ${price}""",
        "select_plan": "Пожалуйста, выберите план:",
        "back_to_menu": "↩️ Вернуться в меню",
        "payment_settings": "💳 Настройки оплаты",
        "current_payment_settings": """*Текущие настройки оплаты*

Идентификатор продавца: `{merchant_id}`
API ключ: `{api_key}`
Валюта: {currency}
Сетевой адрес: {network}

Статус: {status}""",
        "payment_settings_menu": "Выберите, что вы хотите настроить:",
        "set_merchant": "Установить идентификатор продавца",
        "set_api_key": "Установить API ключ",
        "set_currency": "Установить валюту",
        "set_network": "Установить сетевой адрес",
        "test_payment": "Проверить платежную систему",
        "enter_merchant_id": "Пожалуйста, введите идентификатор продавца:",
        "enter_api_key": "Пожалуйста, введите API ключ:",
        "enter_currency": "Пожалуйста, введите валюту (например, USDT):",
        "enter_network": "Пожалуйста, введите сетевой адрес (например, tron):",
        "settings_updated": "✅ Настройки успешно обновлены!",
        "test_success": "✅ Платежная система работает правильно!",
        "test_failed": "❌ Тестирование платежной системы не удалось: {error}",
        "select_platform": "Выберите вашу платформу:",
        "android_store": "📱 Android (Play Store)",
        "android_direct": "📱 Android (Прямой APK)",
        "ios": "📱 iOS (App Store)",
        "windows": "💻 Windows",
        "other_platforms": "🌐 Другие платформы",
        "download_title": "📶 Скачать Hiddify",
        "download_links": """*Доступные ссылки для загрузки:*

📱 *Android:*
• [Play Store](https://play.google.com/store/apps/details?id=app.hiddify.com)
• [Прямой APK](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Android-arm64.apk)

📱 *iOS:*
• [App Store](https://apps.apple.com/us/app/hiddify-proxy-vpn/id6596777532)

💻 *Windows:*
• [Скачать установщик](https://github.com/hiddify/hiddify-next/releases/download/v2.5.7/Hiddify-Windows-Setup-x64.exe)

🌐 *Другие платформы:*
• [GitHub Releases](https://github.com/hiddify/hiddify-app/releases/tag/v2.5.7)""",
        "spam_warning": "⚠️ Предупреждение: Вы отправляете сообщения слишком быстро. ({current}/{limit} сообщений)",
        "spam_blocked": "🚫 Вы были заблокированы на {duration} секунд за спам.",
        "spam_wait": "Ваш аккаунт временно заблокирован за спам. Пожалуйста, подождите {time} секунд.",
        "test_mode_config": "🧪 Тестовый режим: Создание вашей конфигурации...",
        "payment_link_exists": "У вас уже есть активная ссылка оплаты для этого плана. Пожалуйста, подождите {minutes} минут, прежде чем запросить новый, или завершите/отмените текущую оплату.",
        "check_payment": "Проверить статус оплаты",
        "payment_success": "💰 Оплата прошла успешно! Создание вашей конфигурации...",
        "payment_failed": "❌ Оплата не прошла или истекла. Пожалуйста, попробуйте еще раз.",
        "config_error": "Ошибка при создании конфигурации: {error}",
        "uri_error": "Ошибка при получении URI: {error}",
        "config_created": "Конфигурация успешно создана!",
        "your_config": """*Ваша конфигурация VPN*

🔗 *Прямой URI:*
`{direct_uri}`

📱 *SingBox подписка:*
`{singbox_sub}`

🌐 *Обычная подписка:*
`{normal_sub}`

📊 *Детали плана:*
• Трафик: {traffic}GB
• Продолжительность: {days} дней
• Создано: {created_at}""",
        "qr_caption": "QR код для {username}",
        "cli_error": "❌ CLI Command Error: {error}",
        "back_button": "⬅️ Back",
        "cancel_button": "❌ Cancel"
    }
}

def get_text(language_code, key):
    return TRANSLATIONS.get(language_code, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"][key]) 
