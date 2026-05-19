"""
Coffee Pie Translator - QObject exposed to QML for multi-language support.
Usage in QML:  text: tr("Spanish text")
"""
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, Slot, Signal, Property

from translations import TRANSLATIONS, LANGS

TRANSLATIONS_FILE = str(Path(__file__).parent / 'translations.json')


class Translator(QObject):
    langChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lang = 'es'
        self._dict = {}
        self._load_translations()

    def _load_translations(self):
        self._dict = dict(TRANSLATIONS)
        if os.path.exists(TRANSLATIONS_FILE):
            try:
                with open(TRANSLATIONS_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                if saved.get('lang') in LANGS:
                    self._lang = saved['lang']
                self._dict.update(saved.get('translations', {}))
            except (json.JSONDecodeError, IOError):
                pass

    def _save_lang(self):
        try:
            with open(TRANSLATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'lang': self._lang, 'translations': dict(self._dict)}, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    @Slot(str, result=str)
    def tr(self, text):
        if not text or self._lang == 'es':
            return text
        entry = self._dict.get(text)
        if entry and self._lang in entry:
            return entry[self._lang]
        return text

    @Slot(result=str)
    def currentLang(self):
        return self._lang

    @Slot(result=str)
    def currentLangName(self):
        return LANGS.get(self._lang, self._lang)

    @Slot(str)
    def setLang(self, code):
        if code in LANGS:
            self._lang = code
            self._save_lang()
            self.langChanged.emit()

    @Slot(result='QVariantList')
    def availableLangs(self):
        return [{'code': k, 'name': v} for k, v in LANGS.items()]
