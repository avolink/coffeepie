"""
Coffee Pie Translation System.
Supports 11 languages. Default source language is Spanish (es-co).

To add translations: extend the TRANSLATIONS dict with new keys.
"""
from pathlib import Path

LANGS = {
    'es': 'Español',
    'en': 'English',
    'pt': 'Português',
    'fr': 'Français',
    'de': 'Deutsch',
    'ja': '日本語',
    'ru': 'Русский',
    'hi': 'हिन्दी',
    'ar': 'العربية',
    'ko': '한국어',
    'zh': '中文',
}

TRANSLATIONS_FILE = str(Path(__file__).parent / 'translations.json')

TRANSLATIONS = {
    # ── Login Screen ──
    'Coffee Pie®': {
        'en': 'Coffee Pie®', 'pt': 'Coffee Pie®', 'fr': 'Coffee Pie®', 'de': 'Coffee Pie®',
        'ja': 'Coffee Pie®', 'ru': 'Coffee Pie®', 'hi': 'Coffee Pie®', 'ar': 'Coffee Pie®', 'ko': 'Coffee Pie®', 'zh': 'Coffee Pie®',
    },
    'Inicio de Sesión': {
        'en': 'Sign In', 'pt': 'Iniciar Sessão', 'fr': 'Connexion', 'de': 'Anmelden',
        'ja': 'ログイン', 'ru': 'Вход', 'hi': 'लॉग इन', 'ar': 'تسجيل الدخول', 'ko': '로그인', 'zh': '登录',
    },
    'Usuario': {
        'en': 'Username', 'pt': 'Usuário', 'fr': 'Utilisateur', 'de': 'Benutzer',
        'ja': 'ユーザー名', 'ru': 'Пользователь', 'hi': 'उपयोगकर्ता', 'ar': 'المستخدم', 'ko': '사용자', 'zh': '用户名',
    },
    'Contraseña': {
        'en': 'Password', 'pt': 'Senha', 'fr': 'Mot de passe', 'de': 'Passwort',
        'ja': 'パスワード', 'ru': 'Пароль', 'hi': 'पासवर्ड', 'ar': 'كلمة المرور', 'ko': '비밀번호', 'zh': '密码',
    },
    'Crear cuenta nueva': {
        'en': 'Create new account', 'pt': 'Criar nova conta', 'fr': 'Créer un compte', 'de': 'Neues Konto',
        'ja': '新規アカウント作成', 'ru': 'Создать аккаунт', 'hi': 'नया खाता बनाएं', 'ar': 'إنشاء حساب جديد', 'ko': '새 계정 만들기', 'zh': '创建新账户',
    },
    'Restablecer contraseña': {
        'en': 'Reset password', 'pt': 'Redefinir senha', 'fr': 'Réinitialiser mot de passe', 'de': 'Passwort zurücksetzen',
        'ja': 'パスワードをリセット', 'ru': 'Сброс пароля', 'hi': 'पासवर्ड रीसेट करें', 'ar': 'إعادة تعيين كلمة المرور', 'ko': '비밀번호 재설정', 'zh': '重置密码',
    },

    # ── Home Screen ──
    'Mis Máquinas': {
        'en': 'My Machines', 'pt': 'Minhas Máquinas', 'fr': 'Mes Machines', 'de': 'Meine Maschinen',
        'ja': 'マイマシン', 'ru': 'Мои машины', 'hi': 'मेरी मशीनें', 'ar': 'أجهزتي', 'ko': '내 머신', 'zh': '我的机器',
    },
    'Saldo:': {
        'en': 'Balance:', 'pt': 'Saldo:', 'fr': 'Solde:', 'de': 'Guthaben:',
        'ja': '残高:', 'ru': 'Баланс:', 'hi': 'शेष:', 'ar': 'الرصيد:', 'ko': '잔액:', 'zh': '余额:',
    },
    'Tipo Cuenta:': {
        'en': 'Account Type:', 'pt': 'Tipo de Conta:', 'fr': 'Type de compte:', 'de': 'Kontotyp:',
        'ja': 'アカウントタイプ:', 'ru': 'Тип аккаунта:', 'hi': 'खाता प्रकार:', 'ar': 'نوع الحساب:', 'ko': '계정 유형:', 'zh': '账户类型:',
    },
    'Básico': {
        'en': 'Basic', 'pt': 'Básico', 'fr': 'Basique', 'de': 'Einfach',
        'ja': 'ベーシック', 'ru': 'Базовый', 'hi': 'बुनियादी', 'ar': 'أساسي', 'ko': '기본', 'zh': '基础',
    },
    'Avanzado': {
        'en': 'Advanced', 'pt': 'Avançado', 'fr': 'Avancé', 'de': 'Erweitert',
        'ja': 'アドバンスド', 'ru': 'Продвинутый', 'hi': 'उन्नत', 'ar': 'متقدم', 'ko': '고급', 'zh': '高级',
    },

    # ── Main Menu ──
    'Recargar Saldo': {
        'en': 'Recharge Balance', 'pt': 'Recarregar Saldo', 'fr': 'Recharger le solde', 'de': 'Guthaben aufladen',
        'ja': '残高をチャージ', 'ru': 'Пополнить баланс', 'hi': 'शेष राशि रिचार्ज', 'ar': 'إعادة شحن الرصيد', 'ko': '잔액 충전', 'zh': '充值余额',
    },
    'Mi Cuenta': {
        'en': 'My Account', 'pt': 'Minha Conta', 'fr': 'Mon Compte', 'de': 'Mein Konto',
        'ja': 'マイアカウント', 'ru': 'Мой аккаунт', 'hi': 'मेरा खाता', 'ar': 'حسابي', 'ko': '내 계정', 'zh': '我的账户',
    },
    'Configuración': {
        'en': 'Settings', 'pt': 'Configurações', 'fr': 'Paramètres', 'de': 'Einstellungen',
        'ja': '設定', 'ru': 'Настройки', 'hi': 'सेटिंग्स', 'ar': 'الإعدادات', 'ko': '설정', 'zh': '设置',
    },
    'Cerrar Sesión': {
        'en': 'Sign Out', 'pt': 'Sair', 'fr': 'Déconnexion', 'de': 'Abmelden',
        'ja': 'ログアウト', 'ru': 'Выйти', 'hi': 'लॉग आउट', 'ar': 'تسجيل الخروج', 'ko': '로그아웃', 'zh': '退出登录',
    },

    # ── Config Screen ──
    'Configuración Básica': {
        'en': 'Basic Settings', 'pt': 'Configurações Básicas', 'fr': 'Paramètres de base', 'de': 'Grundeinstellungen',
        'ja': '基本設定', 'ru': 'Основные настройки', 'hi': 'बुनियादी सेटिंग्स', 'ar': 'الإعدادات الأساسية', 'ko': '기본 설정', 'zh': '基本设置',
    },
    'Configuración Avanzada': {
        'en': 'Advanced Settings', 'pt': 'Configurações Avançadas', 'fr': 'Paramètres avancés', 'de': 'Erweiterte Einstellungen',
        'ja': '詳細設定', 'ru': 'Расширенные настройки', 'hi': 'उन्नत सेटिंग्स', 'ar': 'إعدادات متقدمة', 'ko': '고급 설정', 'zh': '高级设置',
    },
    'Lenguaje de Interfaz': {
        'en': 'Interface Language', 'pt': 'Idioma da Interface', 'fr': 'Langue de l\'interface', 'de': 'Oberflächensprache',
        'ja': 'インターフェース言語', 'ru': 'Язык интерфейса', 'hi': 'इंटरफ़ेस भाषा', 'ar': 'لغة الواجهة', 'ko': '인터페이스 언어', 'zh': '界面语言',
    },
    'Conexión Predeterminada': {
        'en': 'Default Connection', 'pt': 'Conexão Padrão', 'fr': 'Connexion par défaut', 'de': 'Standardverbindung',
        'ja': 'デフォルト接続', 'ru': 'Подключение по умолчанию', 'hi': 'डिफ़ॉल्ट कनेक्शन', 'ar': 'الاتصال الافتراضي', 'ko': '기본 연결', 'zh': '默认连接',
    },
    'Codec Predeterminado': {
        'en': 'Default Codec', 'pt': 'Codec Padrão', 'fr': 'Codec par défaut', 'de': 'Standard-Codec',
        'ja': 'デフォルトコーデック', 'ru': 'Кодек по умолчанию', 'hi': 'डिफ़ॉल्ट कोडेक', 'ar': 'الترميز الافتراضي', 'ko': '기본 코덱', 'zh': '默认编解码器',
    },
    'Resolución Predeterminada': {
        'en': 'Default Resolution', 'pt': 'Resolução Padrão', 'fr': 'Résolution par défaut', 'de': 'Standardauflösung',
        'ja': 'デフォルト解像度', 'ru': 'Разрешение по умолчанию', 'hi': 'डिफ़ॉल्ट रिज़ॉल्यूशन', 'ar': 'الدقة الافتراضية', 'ko': '기본 해상도', 'zh': '默认分辨率',
    },
    'Bitrate Predeterminado': {
        'en': 'Default Bitrate', 'pt': 'Bitrate Padrão', 'fr': 'Bitrate par défaut', 'de': 'Standard-Bitrate',
        'ja': 'デフォルトビットレート', 'ru': 'Битрейт по умолчанию', 'hi': 'डिफ़ॉल्ट बिटरेट', 'ar': 'معدل البت الافتراضي', 'ko': '기본 비트레이트', 'zh': '默认比特率',
    },
    'Recurrencia Predeterminada': {
        'en': 'Default Recurrence', 'pt': 'Recorrência Padrão', 'fr': 'Récurrence par défaut', 'de': 'Standard-Wiederholung',
        'ja': 'デフォルトの繰り返し', 'ru': 'Повторение по умолчанию', 'hi': 'डिफ़ॉल्ट पुनरावृत्ति', 'ar': 'التكرار الافتراضي', 'ko': '기본 반복', 'zh': '默认重复',
    },
    'Estado Predeterminado Máquina': {
        'en': 'Default Machine State', 'pt': 'Estado Padrão da Máquina', 'fr': 'État par défaut de la machine', 'de': 'Standard-Maschinenstatus',
        'ja': 'デフォルトマシン状態', 'ru': 'Состояние машины по умолчанию', 'hi': 'डिफ़ॉल्ट मशीन स्थिति', 'ar': 'حالة الجهاز الافتراضية', 'ko': '기본 머신 상태', 'zh': '默认机器状态',
    },
    'Sincronización de Datos': {
        'en': 'Data Sync', 'pt': 'Sincronização de Dados', 'fr': 'Synchro des données', 'de': 'Datensynchronisation',
        'ja': 'データ同期', 'ru': 'Синхронизация данных', 'hi': 'डेटा सिंक', 'ar': 'مزامنة البيانات', 'ko': '데이터 동기화', 'zh': '数据同步',
    },
    'Cargar Valores Predeterminados': {
        'en': 'Load Defaults', 'pt': 'Carregar Padrões', 'fr': 'Charger les valeurs par défaut', 'de': 'Standardwerte laden',
        'ja': 'デフォルトを読み込む', 'ru': 'Загрузить по умолчанию', 'hi': 'डिफ़ॉल्ट लोड करें', 'ar': 'تحميل الافتراضيات', 'ko': '기본값 불러오기', 'zh': '加载默认值',
    },
    'Guardar Cambios': {
        'en': 'Save Changes', 'pt': 'Salvar Alterações', 'fr': 'Enregistrer', 'de': 'Änderungen speichern',
        'ja': '変更を保存', 'ru': 'Сохранить изменения', 'hi': 'परिवर्तन सहेजें', 'ar': 'حفظ التغييرات', 'ko': '변경 사항 저장', 'zh': '保存更改',
    },
    'URL Orquestador': {
        'en': 'Orchestrator URL', 'pt': 'URL do Orquestrador', 'fr': 'URL de l\'orchestrateur', 'de': 'Orchestrator-URL',
        'ja': 'オーケストレーターURL', 'ru': 'URL оркестратора', 'hi': 'ऑर्केस्ट्रेटर URL', 'ar': 'رابط المنظم', 'ko': '오케스트레이터 URL', 'zh': '编排器URL',
    },

    # ── Config Network ──
    'Red y Conectividad': {
        'en': 'Network & Connectivity', 'pt': 'Rede e Conectividade', 'fr': 'Réseau et connectivité', 'de': 'Netzwerk & Konnektivität',
        'ja': 'ネットワークと接続', 'ru': 'Сеть и подключение', 'hi': 'नेटवर्क और कनेक्टिविटी', 'ar': 'الشبكة والاتصال', 'ko': '네트워크 및 연결', 'zh': '网络与连接',
    },
    'Nivel de Red': {
        'en': 'Network Tier', 'pt': 'Nível de Rede', 'fr': 'Niveau réseau', 'de': 'Netzwerkstufe',
        'ja': 'ネットワーク層', 'ru': 'Уровень сети', 'hi': 'नेटवर्क स्तर', 'ar': 'مستوى الشبكة', 'ko': '네트워크 계층', 'zh': '网络层级',
    },
    'Orquestadores': {
        'en': 'Orchestrators', 'pt': 'Orquestradores', 'fr': 'Orchestrateurs', 'de': 'Orchestratoren',
        'ja': 'オーケストレーター', 'ru': 'Оркестраторы', 'hi': 'ऑर्केस्ट्रेटर', 'ar': 'المنسقون', 'ko': '오케스트레이터', 'zh': '编排器',
    },
    'Obtener credenciales TURN': {
        'en': 'Get TURN credentials', 'pt': 'Obter credenciais TURN', 'fr': 'Obtenir identifiants TURN', 'de': 'TURN-Anmeldedaten holen',
        'ja': 'TURN認証情報を取得', 'ru': 'Получить учетные данные TURN', 'hi': 'TURN क्रेडेंशियल प्राप्त करें', 'ar': 'الحصول على بيانات اعتماد TURN', 'ko': 'TURN 자격 증명 가져오기', 'zh': '获取TURN凭证',
    },

    # ── Payment Gateways ──
    'PASARELAS DE PAGO': {
        'en': 'PAYMENT GATEWAYS', 'pt': 'GATEWAYS DE PAGAMENTO', 'fr': 'PASSERELLES DE PAIEMENT', 'de': 'ZAHLUNGSGATEWAYS',
        'ja': '支払いゲートウェイ', 'ru': 'ПЛАТЕЖНЫЕ ШЛЮЗЫ', 'hi': 'भुगतान गेटवे', 'ar': 'بوابات الدفع', 'ko': '결제 게이트웨이', 'zh': '支付网关',
    },
    'Compra exitosa': {
        'en': 'Purchase successful', 'pt': 'Compra realizada', 'fr': 'Achat réussi', 'de': 'Kauf erfolgreich',
        'ja': '購入完了', 'ru': 'Покупка успешна', 'hi': 'खरीद सफल', 'ar': 'تم الشراء بنجاح', 'ko': '구매 성공', 'zh': '购买成功',
    },

    # ── Pago Seguro ──
    'PAGO SEGURO': {
        'en': 'SECURE PAYMENT', 'pt': 'PAGAMENTO SEGURO', 'fr': 'PAIEMENT SÉCURISÉ', 'de': 'SICHERE ZAHLUNG',
        'ja': '安全な支払い', 'ru': 'БЕЗОПАСНЫЙ ПЛАТЕЖ', 'hi': 'सुरक्षित भुगतान', 'ar': 'دفع آمن', 'ko': '안전한 결제', 'zh': '安全支付',
    },
    'Escanea el código QR con tu app Bancolombia': {
        'en': 'Scan QR code with your Bancolombia app', 'pt': 'Escaneie o código QR com seu app Bancolombia', 'fr': 'Scannez le QR avec votre app Bancolombia', 'de': 'QR-Code mit Bancolombia-App scannen',
        'ja': 'BancolombiaアプリでQRコードをスキャン', 'ru': 'Отсканируйте QR-код в приложении Bancolombia', 'hi': 'Bancolombia ऐप से QR कोड स्कैन करें', 'ar': 'امسح رمز QR باستخدام تطبيق Bancolombia', 'ko': 'Bancolombia 앱으로 QR 코드 스캔', 'zh': '使用Bancolombia应用扫描二维码',
    },
    'Datos de Transferencia Bancaria': {
        'en': 'Bank Transfer Details', 'pt': 'Dados da Transferência', 'fr': 'Détails du virement', 'de': 'Banküberweisungsdaten',
        'ja': '銀行振込詳細', 'ru': 'Данные банковского перевода', 'hi': 'बैंक ट्रांसफर विवरण', 'ar': 'تفاصيل التحويل المصرفي', 'ko': '은행 송금 정보', 'zh': '银行转账详情',
    },
    'Ya realicé el pago': {
        'en': 'I already paid', 'pt': 'Já realizei o pagamento', 'fr': 'J\'ai déjà payé', 'de': 'Ich habe bereits bezahlt',
        'ja': '支払い済み', 'ru': 'Я уже оплатил', 'hi': 'मैंने भुगतान कर दिया', 'ar': 'لقد دفعت بالفعل', 'ko': '이미 결제했습니다', 'zh': '我已付款',
    },
    'Paquete Pequeño': {
        'en': 'Small Package', 'pt': 'Pacote Pequeno', 'fr': 'Petit forfait', 'de': 'Kleines Paket',
        'ja': 'スモールパッケージ', 'ru': 'Малый пакет', 'hi': 'छोटा पैकेज', 'ar': 'الباقة الصغيرة', 'ko': '소형 패키지', 'zh': '小型套餐',
    },
    'Paquete Mediano': {
        'en': 'Medium Package', 'pt': 'Pacote Médio', 'fr': 'Forfait moyen', 'de': 'Mittleres Paket',
        'ja': 'ミディアムパッケージ', 'ru': 'Средний пакет', 'hi': 'मध्यम पैकेज', 'ar': 'الباقة المتوسطة', 'ko': '중형 패키지', 'zh': '中型套餐',
    },
    'Paquete Grande': {
        'en': 'Large Package', 'pt': 'Pacote Grande', 'fr': 'Grand forfait', 'de': 'Großes Paket',
        'ja': 'ラージパッケージ', 'ru': 'Большой пакет', 'hi': 'बड़ा पैकेज', 'ar': 'الباقة الكبيرة', 'ko': '대형 패키지', 'zh': '大型套餐',
    },
    'MÁS POPULAR': {
        'en': 'MOST POPULAR', 'pt': 'MAIS POPULAR', 'fr': 'LE PLUS POPULAIRE', 'de': 'AM BELIEBTESTEN',
        'ja': '一番人気', 'ru': 'САМЫЙ ПОПУЛЯРНЫЙ', 'hi': 'सबसे लोकप्रिय', 'ar': 'الأكثر شعبية', 'ko': '가장 인기있는', 'zh': '最受欢迎',
    },
    'Créditos': {
        'en': 'Credits', 'pt': 'Créditos', 'fr': 'Crédits', 'de': 'Guthaben',
        'ja': 'クレジット', 'ru': 'Кредиты', 'hi': 'क्रेडिट', 'ar': 'ائتمانات', 'ko': '크레딧', 'zh': '积分',
    },

    # ── My Account ──
    'Organización (Nombre Comercial)': {
        'en': 'Organization (Trade Name)', 'pt': 'Organização (Nome Comercial)', 'fr': 'Organisation (Nom commercial)', 'de': 'Organisation (Handelsname)',
        'ja': '組織（商号）', 'ru': 'Организация (Торговое название)', 'hi': 'संगठन (व्यापार नाम)', 'ar': 'المنظمة (الاسم التجاري)', 'ko': '조직 (상호명)', 'zh': '组织（商业名称）',
    },
    'Correo Electrónico Sistemas': {
        'en': 'IT Email', 'pt': 'E-mail de TI', 'fr': 'Email informatique', 'de': 'IT-E-Mail',
        'ja': 'ITメール', 'ru': 'Email IT', 'hi': 'आईटी ईमेल', 'ar': 'البريد الإلكتروني لتقنية المعلومات', 'ko': 'IT 이메일', 'zh': 'IT邮箱',
    },
    'Nombre de Contacto': {
        'en': 'Contact Name', 'pt': 'Nome de Contato', 'fr': 'Nom du contact', 'de': 'Kontaktname',
        'ja': '連絡先名', 'ru': 'Имя контакта', 'hi': 'संपर्क नाम', 'ar': 'اسم جهة الاتصال', 'ko': '연락처 이름', 'zh': '联系人姓名',
    },
    'Número de Contacto': {
        'en': 'Contact Number', 'pt': 'Número de Contato', 'fr': 'Numéro de contact', 'de': 'Kontaktnummer',
        'ja': '連絡先番号', 'ru': 'Номер контакта', 'hi': 'संपर्क नंबर', 'ar': 'رقم الاتصال', 'ko': '연락처 번호', 'zh': '联系电话',
    },
    'Sitio Web': {
        'en': 'Website', 'pt': 'Site', 'fr': 'Site web', 'de': 'Webseite',
        'ja': 'ウェブサイト', 'ru': 'Веб-сайт', 'hi': 'वेबसाइट', 'ar': 'الموقع الإلكتروني', 'ko': '웹사이트', 'zh': '网站',
    },
    'Dominio': {
        'en': 'Domain', 'pt': 'Domínio', 'fr': 'Domaine', 'de': 'Domäne',
        'ja': 'ドメイン', 'ru': 'Домен', 'hi': 'डोमेन', 'ar': 'النطاق', 'ko': '도메인', 'zh': '域名',
    },
    'Dirección Física': {
        'en': 'Physical Address', 'pt': 'Endereço Físico', 'fr': 'Adresse physique', 'de': 'Physische Adresse',
        'ja': '住所', 'ru': 'Физический адрес', 'hi': 'भौतिक पता', 'ar': 'العنوان الفعلي', 'ko': '물리적 주소', 'zh': '物理地址',
    },
}
