import os
import uuid
import edge_tts
from datetime import datetime
from core.providers.tts.base import TTSProviderBase

# Mapping lingua -> voce Edge TTS
# Voci neurali per diverse lingue
LANG_VOICES = {
    # Italiano (default)
    "it": "it-IT-ElsaNeural",
    # Cinese
    "zh": "zh-CN-XiaoxiaoNeural",
    # Giapponese
    "ja": "ja-JP-NanamiNeural",
    # Coreano
    "ko": "ko-KR-SunHiNeural",
    # Russo
    "ru": "ru-RU-SvetlanaNeural",
    # Arabo
    "ar": "ar-SA-ZariyahNeural",
    # Hindi
    "hi": "hi-IN-SwaraNeural",
    # Greco
    "el": "el-GR-AthinaNeural",
    # Inglese
    "en": "en-US-JennyNeural",
    # Francese
    "fr": "fr-FR-DeniseNeural",
    # Spagnolo
    "es": "es-ES-ElviraNeural",
    # Tedesco
    "de": "de-DE-KatjaNeural",
    # Portoghese
    "pt": "pt-BR-FranciscaNeural",
    # Olandese
    "nl": "nl-NL-ColetteNeural",
    # Polacco
    "pl": "pl-PL-ZofiaNeural",
    # Turco
    "tr": "tr-TR-EmelNeural",
}


def detect_text_language(text: str) -> str:
    """
    Rileva la lingua del testo basandosi sui caratteri.
    Ritorna codice lingua per selezionare voce TTS appropriata.
    """
    if not text or not text.strip():
        return "it"  # default italiano

    text = text.strip()

    # Conta caratteri per tipo di script
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    japanese_kana = sum(1 for c in text if '\u3040' <= c <= '\u30ff')
    korean = sum(1 for c in text if '\uac00' <= c <= '\ud7af' or '\u1100' <= c <= '\u11ff')
    cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04ff')
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    greek = sum(1 for c in text if '\u0370' <= c <= '\u03ff')
    devanagari = sum(1 for c in text if '\u0900' <= c <= '\u097f')

    total = len(text.replace(" ", ""))
    if total == 0:
        return "it"

    # Soglia 20% per rilevamento
    threshold = 0.2

    if chinese / total > threshold:
        # Distingui cinese da giapponese (giapponese ha anche kana)
        if japanese_kana > 0:
            return "ja"
        return "zh"
    if japanese_kana / total > 0.1:
        return "ja"
    if korean / total > threshold:
        return "ko"
    if cyrillic / total > threshold:
        return "ru"
    if arabic / total > threshold:
        return "ar"
    if greek / total > threshold:
        return "el"
    if devanagari / total > threshold:
        return "hi"

    # Per lingue latine, mantieni voce configurata (italiano di default)
    return None  # None = usa voce default configurata


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        if config.get("private_voice"):
            self.voice = config.get("private_voice")
        else:
            self.voice = config.get("voice")
        self.default_voice = self.voice  # Salva voce default
        self.audio_file_type = config.get("format", "mp3")
        self.auto_detect_language = config.get("auto_detect_language", True)

    def generate_filename(self, extension=".mp3"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    def get_voice_for_text(self, text: str) -> str:
        """Seleziona la voce appropriata in base alla lingua del testo"""
        if not self.auto_detect_language:
            return self.default_voice

        detected_lang = detect_text_language(text)
        if detected_lang and detected_lang in LANG_VOICES:
            return LANG_VOICES[detected_lang]
        return self.default_voice

    async def text_to_speak(self, text, output_file):
        try:
            # Rileva lingua e seleziona voce appropriata
            voice = self.get_voice_for_text(text)
            communicate = edge_tts.Communicate(text, voice=voice)
            if output_file:
                # 确保目录存在并创建空文件
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "wb") as f:
                    pass

                # 流式写入音频数据
                with open(output_file, "ab") as f:  # 改为追加模式避免覆盖
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":  # 只处理音频数据块
                            f.write(chunk["data"])
            else:
                # 返回音频二进制数据
                audio_bytes = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes += chunk["data"]
                return audio_bytes
        except Exception as e:
            error_msg = f"Edge TTS请求失败: {e}"
            raise Exception(error_msg)  # 抛出异常，让调用方捕获