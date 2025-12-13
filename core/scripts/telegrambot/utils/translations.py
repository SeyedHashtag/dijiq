from typing import Dict

# Available languages
LANGUAGES = {
    "en": "English 🇬🇧",
    "fa": "Persian 🇮🇷",
    "tk": "Turkmen 🇹🇲"
}

# Default language
DEFAULT_LANGUAGE = "en"

# Button translations for non-admin menu
BUTTON_TRANSLATIONS = {
    "en": {
        "my_configs": "📱 My Configs",
        "purchase_plan": "💰 Purchase Plan",
        "downloads": "⬇️ Downloads",
        "test_config": "🎁 Test Config",
        "support": "📞 Support",
        "language": "🌐 Language/زبان",
        "confirm": "✅ Confirm",
        "cancel": "❌ Cancel",
        "crypto": "💳 Crypto",
        "card_to_card": "📄 Card to Card (Iran)",
        "payment_link": "🔗 Payment Link",
        "check_status": "🔄 Check Status"
    },
    "fa": {
        "my_configs": "📱 پیکربندی‌های من",
        "purchase_plan": "💰 خرید طرح",
        "downloads": "⬇️ دانلودها",
        "test_config": "🎁 پیکربندی آزمایشی",
        "support": "📞 پشتیبانی",
        "language": "🌐 Language/زبان",
        "confirm": "✅ تایید",
        "cancel": "❌ لغو",
        "crypto": "💳 کریپتو",
        "card_to_card": "📄 کارت به کارت (ایران)",
        "payment_link": "🔗 لینک پرداخت",
        "check_status": "🔄 بررسی وضعیت"
    },
    "tk": {
        "my_configs": "📱 Meniň sazlamalarym",
        "purchase_plan": "💰 Meýilnama satyn al",
        "downloads": "⬇️ Ýüklemeler",
        "test_config": "🎁 Synag sazlamalary",
        "support": "📞 Goldaw",
        "language": "🌐 Language/Dil",
        "confirm": "✅ Tassykla",
        "cancel": "❌ Ýatyr",
        "crypto": "💳 Kripto",
        "card_to_card": "📄 Karta kart (Eýran)",
        "payment_link": "🔗 Töleg baglanyşygy",
        "check_status": "🔄 Statusy barlaň"
    }
}

# Messages translations
MESSAGE_TRANSLATIONS = {
    "en": {
        "select_platform": "🔴 **Important: Select your actual country in the software.",
        "no_active_configs": "❌ You don't have any active configurations.\n\nPlease use the '🎁 Test Config' button to get a free test config or the '💰 Purchase Plan' button to buy a subscription.",
        "test_config_used": "⚠️ You have already used your free test config. Please purchase a plan for continued service.",
        "select_plan": "📱 Select a plan to purchase:",
        "unlimited_users": " (Unlimited Users)",
        "single_user": " (Single User)",
        "plan_details": "📋 Plan Details:\n\n",
        "data": "📊 Data: {plan_gb} GB\n",
        "price": "💰 Price: ${price}\n",
        "duration": "📅 Duration: {days} days\n",
        "unlimited": "♾️ Unlimited Users: {unlimited_text}\n\n",
        "proceed_with_payment": "Proceed with payment?",
        "plan_not_found": "Plan not found!",
        "purchase_canceled": "Purchase canceled.",
        "no_payment_methods": "No payment methods are currently configured. Please contact support.",
        "select_payment_method": "Please select your preferred payment method:",
        "invalid_payment_method": "Invalid payment method!",
        "error_creating_payment": "❌ Error creating payment: {error}",
        "invalid_payment_response": "❌ Invalid payment response from payment gateway.",
        "payment_instructions": "💰 Payment Instructions\n\n1. Scan the QR code or click the link below\n2. Complete the payment of ${price}\n3. Your config will be created automatically once payment is confirmed\n\nPayment Link: {payment_url}\n\nPayment ID: `{payment_id}`",
        "error_processing_payment": "Error processing payment: {error}",
        "card_to_card_not_configured": "Card to Card payment is not configured. Please contact support.",
        "card_to_card_payment": "📄 Card to Card Payment\n\nPlease transfer `{price}` Tomans to the following card number:\n\n`{card_number}`\n\nAfter the transfer, please send a photo of the receipt.",
        "upload_receipt": "Please upload a photo of the receipt.",
        "receipt_submitted": "Your receipt has been submitted for approval. You will be notified once it is processed.",
        "error_occurred": "An error occurred: {error}",
        "not_authorized": "You are not authorized to perform this action.",
        "payment_record_not_found": "Payment record not found!",
        "payment_already_processed": "This payment has already been processed and has a status of '{status}'.",
        "payment_approved": "✅ Your payment has been approved and your plan is active!\n\n📊 Plan: {plan_gb} GB\n📅 Duration: {days} days\n📱 Username: `{username}`\n\nSubscription URL: `{sub_url}`",
        "payment_approved_no_url": "✅ Your payment was approved, but there was an error retrieving your subscription URL. Please contact support.",
        "failed_to_create_user": "Failed to create user. Please check the logs.",
        "payment_approved_user_error": "❌ Your payment was approved, but there was an error creating your account. Please contact support.",
        "payment_rejected": "❌ Your payment has been rejected. Please contact support if you believe this is an error.",
        "payment_pending": "Payment is still pending. Please complete the payment.",
        "payment_status": "Payment status: {status}",
        "payment_completed": "✅ Payment completed!\n\n📊 Your {plan_gb}GB plan is ready.\n📱 Username: `{username}`\n\nSubscription URL: `{sub_url}`\n\nScan the QR code to configure your VPN.",
        "payment_completed_no_url": "✅ Payment completed and account created, but couldn't generate subscription URL. Please contact support.",
        "payment_completed_user_error": "✅ Payment completed but error creating account. Please contact support.",
        "scan_qr_code": "Scan this QR code to configure your VPN client.",
        "payment_notification_title": "Payment Notification",
        "successful_payment_received": "Successful Payment Received",
        "user_id": "User ID",
        "username": "Username",
        "plan_size": "Plan Size",
        "amount": "Amount",
        "payment_method_label": "Payment Method",
        "payment_id_label": "Payment ID",
        "timestamp": "Timestamp"
    },
    "fa": {
        "select_platform": "🔴 **مهم: در نرم افزار، کشور ایران را انتخاب کنید.",
        "no_active_configs": "❌ شما هیچ پیکربندی فعالی ندارید.\n\nلطفاً از دکمه '🎁 پیکربندی آزمایشی' برای دریافت پیکربندی آزمایشی رایگان یا دکمه '💰 پرداخت با رمزارز' برای خرید اشتراک استفاده کنید.",
        "test_config_used": "⚠️ شما قبلاً از پیکربندی آزمایشی رایگان خود استفاده کرده‌اید. لطفاً برای ادامه خدمات، یک اشتراک خریداری کنید.",
        "select_plan": "📱 یک طرح برای خرید انتخاب کنید:",
        "unlimited_users": " (کاربر نامحدود)",
        "single_user": " (تک کاربر)",
        "plan_details": "📋 جزئیات طرح:\n\n",
        "data": "📊 داده: {plan_gb} گیگابایت\n",
        "price": "💰 قیمت: ${price}\n",
        "duration": "📅 مدت زمان: {days} روز\n",
        "unlimited": "♾️ کاربران نامحدود: {unlimited_text}\n\n",
        "proceed_with_payment": "پرداخت را ادامه می دهید؟",
        "plan_not_found": "طرح پیدا نشد!",
        "purchase_canceled": "خرید لغو شد.",
        "no_payment_methods": "در حال حاضر هیچ روش پرداختی پیکربندی نشده است. لطفاً با پشتیبانی تماس بگیرید.",
        "select_payment_method": "لطفاً روش پرداخت مورد نظر خود را انتخاب کنید:",
        "invalid_payment_method": "روش پرداخت نامعتبر است!",
        "error_creating_payment": "❌ خطا در ایجاد پرداخت: {error}",
        "invalid_payment_response": "❌ پاسخ نامعتبر از درگاه پرداخت.",
        "payment_instructions": "💰 دستورالعمل پرداخت\n\n۱. کد QR را اسکن کنید یا روی لینک زیر کلیک کنید\n۲. پرداخت ${price} را تکمیل کنید\n۳. پس از تأیید پرداخت، پیکربندی شما به طور خودکار ایجاد می شود\n\nلینک پرداخت: {payment_url}\n\nشناسه پرداخت: `{payment_id}`",
        "error_processing_payment": "خطا در پردازش پرداخت: {error}",
        "card_to_card_not_configured": "پرداخت کارت به کارت پیکربندی نشده است. لطفاً با پشتیبانی تماس بگیرید.",
        "card_to_card_payment": "📄 پرداخت کارت به کارت\n\nلطفاً `{price}` تومان را به شماره کارت زیر انتقال دهید:\n\n`{card_number}`\n\nپس از انتقال، لطفاً عکسی از رسید را ارسال کنید.",
        "upload_receipt": "لطفاً عکسی از رسید را بارگذاری کنید.",
        "receipt_submitted": "رسید شما برای تأیید ارسال شد. پس از پردازش به شما اطلاع داده خواهد شد.",
        "error_occurred": "خطایی روی داد: {error}",
        "not_authorized": "شما مجاز به انجام این عمل نیستید.",
        "payment_record_not_found": "سوابق پرداخت پیدا نشد!",
        "payment_already_processed": "این پرداخت قبلاً پردازش شده و وضعیت آن '{status}' است.",
        "payment_approved": "✅ پرداخت شما تأیید شد و طرح شما فعال است!\n\n📊 طرح: {plan_gb} گیگابایت\n📅 مدت زمان: {days} روز\n📱 نام کاربری: `{username}`\n\nURL اشتراک: `{sub_url}`",
        "payment_approved_no_url": "✅ پرداخت شما تأیید شد، اما در بازیابی URL اشتراک شما خطایی روی داد. لطفاً با پشتیبانی تماس بگیرید.",
        "failed_to_create_user": "ایجاد کاربر ناموفق بود. لطفاً لاگ ها را بررسی کنید.",
        "payment_approved_user_error": "❌ پرداخت شما تأیید شد، اما در ایجاد حساب شما خطایی روی داد. لطفاً با پشتیبانی تماس بگیرید.",
        "payment_rejected": "❌ پرداخت شما رد شد. اگر فکر می کنید این یک خطا است، لطفاً با پشتیبانی تماس بگیرید.",
        "payment_pending": "پرداخت هنوز در حال انتظار است. لطفاً پرداخت را تکمیل کنید.",
        "payment_status": "وضعیت پرداخت: {status}",
        "payment_completed": "✅ پرداخت با موفقیت انجام شد!\n\n📊 طرح {plan_gb} گیگابایتی شما آماده است.\n📱 نام کاربری: `{username}`\n\nURL اشتراک: `{sub_url}`\n\nبرای پیکربندی VPN خود، کد QR را اسکن کنید.",
        "payment_completed_no_url": "✅ پرداخت با موفقیت انجام شد و حساب ایجاد شد، اما امکان ایجاد URL اشتراک وجود نداشت. لطفاً با پشتیبانی تماس بگیرید.",
        "payment_completed_user_error": "✅ پرداخت با موفقیت انجام شد اما در ایجاد حساب خطایی روی داد. لطفاً با پشتیبانی تماس بگیرید.",
        "scan_qr_code": "برای پیکربندی کلاینت VPN خود، این کد QR را اسکن کنید.",
        "payment_notification_title": "اعلان پرداخت",
        "successful_payment_received": "پرداخت موفق دریافت شد",
        "user_id": "شناسه کاربری",
        "username": "نام کاربری",
        "plan_size": "حجم طرح",
        "amount": "مبلغ",
        "payment_method_label": "روش پرداخت",
        "payment_id_label": "شناسه پرداخت",
        "timestamp": "مهر زمانی"
    },
    "tk": {
        "select_platform": "🔴 ** Möhüm: Programma üpjünçiliginde hakyky ýurduňyzy saýlaň.",
        "no_active_configs": "❌ Siziň işjeň sazlamalaňyz ýok.\n\nMugt synag sazlamasyny almak üçin '🎁 Synag sazlamalary' düwmesini ýa-da abunalyk satyn almak üçin '💰 Kripto bilen töle' düwmesini ulanyň.",
        "test_config_used": "⚠️ Siz eýýäm mugt synag sazlamaňyzy ulanypsyňyz. Hyzmaty dowam etdirmek üçin meýilnama satyn alyň.",
        "select_plan": "📱 Satyn almak üçin meýilnama saýlaň:",
        "unlimited_users": " (Limitsiz ulanyjylar)",
        "single_user": " (Bir ulanyjy)",
        "plan_details": "📋 Meýilnama maglumatlary:\n\n",
        "data": "📊 Maglumatlar: {plan_gb} GB\n",
        "price": "💰 Baha: ${price}\n",
        "duration": "📅 Dowamlylygy: {days} gün\n",
        "unlimited": "♾️ Limitsiz ulanyjylar: {unlimited_text}\n\n",
        "proceed_with_payment": "Tölegi dowam etdiriňmi?",
        "plan_not_found": "Meýilnama tapylmady!",
        "purchase_canceled": "Satyn almak ýatyryldy.",
        "no_payment_methods": "Häzirki wagtda hiç hili töleg usuly sazlanmadyk. Goldaw bilen habarlaşyň.",
        "select_payment_method": "Islän töleg usulyňyzy saýlaň:",
        "invalid_payment_method": "Nädogry töleg usuly!",
        "error_creating_payment": "❌ Töleg döredilende ýalňyşlyk: {error}",
        "invalid_payment_response": "❌ Töleg şlýuzasyndan nädogry jogap.",
        "payment_instructions": "💰 Töleg görkezmeleri\n\n1. QR kody skanirläň ýa-da aşakdaky baglanyşyga basyň\n2. ${price} tölegini tamamlaň\n3. Töleg tassyklanandan soň konfigurasiýaňyz awtomatiki usulda dörediler\n\nTöleg baglanyşygy: {payment_url}\n\nTöleg belgisi: `{payment_id}`",
        "error_processing_payment": "Töleg işlenende ýalňyşlyk: {error}",
        "card_to_card_not_configured": "Karta kart tölegi sazlanmadyk. Goldaw bilen habarlaşyň.",
        "card_to_card_payment": "📄 Karta kart tölegi\n\n`{price}` toman geçiriň:\n\n`{card_number}`\n\nGeçirenden soň, kwitansiýanyň suratyny iberiň.",
        "upload_receipt": "Kwitansiýanyň suratyny ýükläň.",
        "receipt_submitted": "Siziň kwitansiýaňyz barlamak üçin tabşyryldy. Işlenenden soň size habar berler.",
        "error_occurred": "Ýalňyşlyk ýüze çykdy: {error}",
        "not_authorized": "Bu amaly ýerine ýetirmäge ygtyýaryňyz ýok.",
        "payment_record_not_found": "Töleg kaydy tapylmady!",
        "payment_already_processed": "Bu töleg eýýäm işlenipdir we statusy '{status}'dyr.",
        "payment_approved": "✅ Tölegiňiz tassyklandy we meýilnamaňyz işjeň!\n\n📊 Meýilnama: {plan_gb} GB\n📅 Dowamlylygy: {days} gün\n📱 Ulanyjy ady: `{username}`\n\nAbuna URL: `{sub_url}`",
        "payment_approved_no_url": "✅ Tölegiňiz tassyklandy, ýöne abuna URL-iňizi almakda ýalňyşlyk ýüze çykdy. Goldaw bilen habarlaşyň.",
        "failed_to_create_user": "Ulanyjy döredip bolmady. Gündelikleri barlaň.",
        "payment_approved_user_error": "❌ Tölegiňiz tassyklandy, ýöne hasabyňyzy döretmekde ýalňyşlyk ýüze çykdy. Goldaw bilen habarlaşyň.",
        "payment_rejected": "❌ Tölegiňiz ret edildi. Eger munuň ýalňyşlykdygyna ynanýan bolsaňyz, goldaw bilen habarlaşyň.",
        "payment_pending": "Töleg henizem garaşylýar. Tölegi tamamlaň.",
        "payment_status": "Töleg statusy: {status}",
        "payment_completed": "✅ Töleg tamamlandy!\n\n📊 Siziň {plan_gb}GB meýilnamaňyz taýýar.\n📱 Ulanyjy ady: `{username}`\n\nAbuna URL: `{sub_url}`\n\nVPN-iňizi sazlamak üçin QR kody skanirläň.",
        "payment_completed_no_url": "✅ Töleg tamamlandy we hasap döredildi, ýöne abuna URL döredip bolmady. Goldaw bilen habarlaşyň.",
        "payment_completed_user_error": "✅ Töleg tamamlandy, ýöne hasap döredilende ýalňyşlyk ýüze çykdy. Goldaw bilen habarlaşyň.",
        "scan_qr_code": "VPN müşderiňizi sazlamak üçin bu QR kody skanirläň.",
        "payment_notification_title": "Töleg bildirişi",
        "successful_payment_received": "Üstünlikli töleg alyndy",
        "user_id": "Ulanyjy belgisi",
        "username": "Ulanyjy ady",
        "plan_size": "Meýilnama ululygy",
        "amount": "Mukdar",
        "payment_method_label": "Töleg usuly",
        "payment_id_label": "Töleg belgisi",
        "timestamp": "Wagt belgisi"
    }
}

def get_button_text(language_code: str, button_key: str) -> str:
    """Get the translated text for a button key in the specified language.
    
    Args:
        language_code: The language code (e.g., 'en', 'fa')
        button_key: The key for the button text to translate
        
    Returns:
        The translated button text, or the English version if translation not found
    """
    if language_code not in BUTTON_TRANSLATIONS:
        language_code = DEFAULT_LANGUAGE
        
    translations = BUTTON_TRANSLATIONS[language_code]
    return translations.get(button_key, BUTTON_TRANSLATIONS[DEFAULT_LANGUAGE].get(button_key, ""))

def get_message_text(language_code: str, message_key: str) -> str:
    """Get the translated text for a message key in the specified language.
    
    Args:
        language_code: The language code (e.g., 'en', 'fa')
        message_key: The key for the message text to translate
        
    Returns:
        The translated message text, or the English version if translation not found
    """
    if language_code not in MESSAGE_TRANSLATIONS:
        language_code = DEFAULT_LANGUAGE
        
    translations = MESSAGE_TRANSLATIONS[language_code]
    return translations.get(message_key, MESSAGE_TRANSLATIONS[DEFAULT_LANGUAGE].get(message_key, ""))

# These functions will be overridden by the implementations in language.py
# They're provided as fallbacks
def get_user_language(user_id: int) -> str:
    """Get the language preference for a user."""
    return DEFAULT_LANGUAGE

def set_user_language(user_id: int, language_code: str) -> None:
    """Set the language preference for a user."""
    pass