import json

file_path = '/home/avolink/DEV/coffeepie/coffeepie_website/public/translations.json'

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

new_translations = {
    "Ir al carrito": {
        "en": "Go to cart",
        "es": "Ir al carrito",
        "pt": "Ir para o carrinho",
        "fr": "Aller au panier",
        "de": "Zum Warenkorb",
        "ru": "Перейти в корзину",
        "hi": "कार्ट पर जाएं",
        "ja": "カートへ進む",
        "zh": "前往购物车",
        "ko": "장바구니로 이동",
        "ar": "الذهاب إلى العربة"
    },
    "Cuenta para Retiros": {
        "en": "Withdrawal Account",
        "es": "Cuenta para Retiros",
        "pt": "Conta para Saques",
        "fr": "Compte de Retrait",
        "de": "Auszahlungskonto",
        "ru": "Счет для Вывода",
        "hi": "निकासी खाता",
        "ja": "出金口座",
        "zh": "提款账户",
        "ko": "출금 계좌",
        "ar": "حساب السحب"
    },
    "Requerido para Proveedores de Nube para convertir tokens a moneda local.": {
        "en": "Required for Cloud Providers to convert tokens to local currency.",
        "es": "Requerido para Proveedores de Nube para convertir tokens a moneda local.",
        "pt": "Obrigatório para Provedores de Nuvem para converter tokens em moeda local.",
        "fr": "Requis pour les Fournisseurs de Cloud pour convertir les jetons en monnaie locale.",
        "de": "Erforderlich für Cloud-Anbieter, um Tokens in lokale Währung umzuwandeln.",
        "ru": "Требуется для Провайдеров Облачных Услуг для конвертации токенов в местную валюту.",
        "hi": "क्लाउड प्रदाताओं के लिए टोकन को स्थानीय मुद्रा में बदलने के लिए आवश्यक है।",
        "ja": "クラウドプロバイダーがトークンを現地通貨に変換するために必要です。",
        "zh": "云提供商需要此项以将代币转换为本地货币。",
        "ko": "클라우드 제공자가 토큰을 현지 통화로 변환하는 데 필요합니다.",
        "ar": "مطلوب لمزودي السحابة لتحويل الرموز إلى عملة محلية."
    },
    "Banco": {
        "en": "Bank",
        "es": "Banco",
        "pt": "Banco",
        "fr": "Banque",
        "de": "Bank",
        "ru": "Банк",
        "hi": "बैंक",
        "ja": "銀行",
        "zh": "银行",
        "ko": "은행",
        "ar": "البنك"
    },
    "Tipo de Cuenta": {
        "en": "Account Type",
        "es": "Tipo de Cuenta",
        "pt": "Tipo de Conta",
        "fr": "Type de Compte",
        "de": "Kontotyp",
        "ru": "Тип Счета",
        "hi": "खाता प्रकार",
        "ja": "口座の種類",
        "zh": "账户类型",
        "ko": "계좌 유형",
        "ar": "نوع الحساب"
    },
    "Selecciona el tipo de cuenta": {
        "en": "Select account type",
        "es": "Selecciona el tipo de cuenta",
        "pt": "Selecione o tipo de conta",
        "fr": "Sélectionnez le type de compte",
        "de": "Wählen Sie den Kontotyp",
        "ru": "Выберите тип счета",
        "hi": "खाता प्रकार चुनें",
        "ja": "口座の種類を選択",
        "zh": "选择账户类型",
        "ko": "계좌 유형 선택",
        "ar": "حدد نوع الحساب"
    },
    "Ahorros": {
        "en": "Savings",
        "es": "Ahorros",
        "pt": "Poupança",
        "fr": "Épargne",
        "de": "Sparkonto",
        "ru": "Сберегательный",
        "hi": "बचत",
        "ja": "普通預金",
        "zh": "储蓄",
        "ko": "저축",
        "ar": "توفير"
    },
    "Corriente": {
        "en": "Checking",
        "es": "Corriente",
        "pt": "Corrente",
        "fr": "Courant",
        "de": "Girokonto",
        "ru": "Текущий",
        "hi": "चालू",
        "ja": "当座預金",
        "zh": "活期",
        "ko": "당좌",
        "ar": "جاري"
    },
    "Número de Cuenta": {
        "en": "Account Number",
        "es": "Número de Cuenta",
        "pt": "Número da Conta",
        "fr": "Numéro de Compte",
        "de": "Kontonummer",
        "ru": "Номер Счета",
        "hi": "खाता संख्या",
        "ja": "口座番号",
        "zh": "账号",
        "ko": "계좌 번호",
        "ar": "رقم الحساب"
    },
    "Guardar Cuenta": {
        "en": "Save Account",
        "es": "Guardar Cuenta",
        "pt": "Salvar Conta",
        "fr": "Enregistrer le Compte",
        "de": "Konto Speichern",
        "ru": "Сохранить Счет",
        "hi": "खाता सहेजें",
        "ja": "口座を保存",
        "zh": "保存账户",
        "ko": "계좌 저장",
        "ar": "حفظ الحساب"
    },
    "Documentos de la Empresa": {
        "en": "Company Documents",
        "es": "Documentos de la Empresa",
        "pt": "Documentos da Empresa",
        "fr": "Documents de l'Entreprise",
        "de": "Unternehmensdokumente",
        "ru": "Документы Компании",
        "hi": "कंपनी के दस्तावेज़",
        "ja": "会社書類",
        "zh": "公司文件",
        "ko": "회사 문서",
        "ar": "مستندات الشركة"
    },
    "Sube los documentos requeridos en formato PDF, JPG o PNG.": {
        "en": "Upload the required documents in PDF, JPG, or PNG format.",
        "es": "Sube los documentos requeridos en formato PDF, JPG o PNG.",
        "pt": "Faça o upload dos documentos necessários em formato PDF, JPG ou PNG.",
        "fr": "Téléchargez les documents requis au format PDF, JPG ou PNG.",
        "de": "Laden Sie die erforderlichen Dokumente im PDF-, JPG- oder PNG-Format hoch.",
        "ru": "Загрузите необходимые документы в формате PDF, JPG или PNG.",
        "hi": "PDF, JPG या PNG प्रारूप में आवश्यक दस्तावेज़ अपलोड करें।",
        "ja": "必要な書類をPDF、JPG、またはPNG形式でアップロードしてください。",
        "zh": "以PDF、JPG或PNG格式上传所需文件。",
        "ko": "PDF, JPG 또는 PNG 형식으로 필수 문서를 업로드하세요.",
        "ar": "قم بتحميل المستندات المطلوبة بتنسيق PDF أو JPG أو PNG."
    },
    "RUT": {
        "en": "RUT",
        "es": "RUT",
        "pt": "RUT",
        "fr": "RUT",
        "de": "RUT",
        "ru": "RUT",
        "hi": "RUT",
        "ja": "RUT",
        "zh": "RUT",
        "ko": "RUT",
        "ar": "RUT"
    },
    "Cámara de Comercio": {
        "en": "Chamber of Commerce",
        "es": "Cámara de Comercio",
        "pt": "Câmara de Comércio",
        "fr": "Chambre de Commerce",
        "de": "Handelskammer",
        "ru": "Торговая Палата",
        "hi": "वाणिज्य मंडल",
        "ja": "商工会議所",
        "zh": "商会",
        "ko": "상공회의소",
        "ar": "الغرفة التجارية"
    },
    "Cédula del Representante Legal": {
        "en": "Legal Representative ID",
        "es": "Cédula del Representante Legal",
        "pt": "Identidade do Representante Legal",
        "fr": "Pièce d'Identité du Représentant Légal",
        "de": "Ausweis des Gesetzlichen Vertreters",
        "ru": "Удостоверение Личности Законного Представителя",
        "hi": "कानूनी प्रतिनिधि का पहचान पत्र",
        "ja": "法定代表者の身分証明書",
        "zh": "法定代表人身份证",
        "ko": "법정 대리인 신분증",
        "ar": "هوية الممثل القانوني"
    },
    "Certificación Bancaria": {
        "en": "Bank Certification",
        "es": "Certificación Bancaria",
        "pt": "Certificação Bancária",
        "fr": "Attestation Bancaire",
        "de": "Bankbestätigung",
        "ru": "Банковская Справка",
        "hi": "बैंक प्रमाणन",
        "ja": "銀行証明書",
        "zh": "银行证明",
        "ko": "은행 증명서",
        "ar": "شهادة بنكية"
    },
    "Subir Documentos": {
        "en": "Upload Documents",
        "es": "Subir Documentos",
        "pt": "Fazer Upload de Documentos",
        "fr": "Télécharger des Documents",
        "de": "Dokumente Hochladen",
        "ru": "Загрузить Документы",
        "hi": "दस्तावेज़ अपलोड करें",
        "ja": "書類をアップロード",
        "zh": "上传文件",
        "ko": "문서 업로드",
        "ar": "تحميل المستندات"
    }
}

data.update(new_translations)

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("Translations updated successfully.")
