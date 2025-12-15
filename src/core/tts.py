"""Text-to-Speech support for Ukrainian pronunciation."""

import platform
import subprocess
import tempfile
from pathlib import Path


class TTSError(Exception):
    """Error during text-to-speech operation."""
    pass


class TextToSpeech:
    """Text-to-speech using Google TTS (gTTS).

    Generates audio for Ukrainian text and plays it using system audio player.
    """

    def __init__(self, lang: str = "uk"):
        """Initialize TTS with language code.

        Args:
            lang: Language code (default: 'uk' for Ukrainian)
        """
        self.lang = lang
        self._gtts_available = None
        self._temp_dir = Path(tempfile.gettempdir()) / "ukr-learn-tts"
        self._temp_dir.mkdir(exist_ok=True)

    def is_available(self) -> bool:
        """Check if TTS is available."""
        if self._gtts_available is None:
            import importlib.util
            self._gtts_available = importlib.util.find_spec("gtts") is not None
        return self._gtts_available

    def speak(self, text: str) -> None:
        """Speak the given text.

        Args:
            text: Text to speak (Ukrainian)

        Raises:
            TTSError: If TTS fails
        """
        if not text or not text.strip():
            return

        if not self.is_available():
            raise TTSError("gTTS not installed. Run: pip install gTTS")

        try:
            from gtts import gTTS

            # Generate audio file
            tts = gTTS(text=text.strip(), lang=self.lang, slow=False)

            # Save to temp file
            audio_file = self._temp_dir / "speech.mp3"
            tts.save(str(audio_file))

            # Play audio
            self._play_audio(audio_file)

        except Exception as e:
            raise TTSError(f"TTS failed: {e}")

    def speak_slow(self, text: str) -> None:
        """Speak the given text slowly (for learning).

        Args:
            text: Text to speak (Ukrainian)
        """
        if not text or not text.strip():
            return

        if not self.is_available():
            raise TTSError("gTTS not installed. Run: pip install gTTS")

        try:
            from gtts import gTTS

            tts = gTTS(text=text.strip(), lang=self.lang, slow=True)
            audio_file = self._temp_dir / "speech_slow.mp3"
            tts.save(str(audio_file))
            self._play_audio(audio_file)

        except Exception as e:
            raise TTSError(f"TTS failed: {e}")

    def _play_audio(self, audio_file: Path) -> None:
        """Play audio file using system player.

        Args:
            audio_file: Path to audio file
        """
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                subprocess.run(
                    ["afplay", str(audio_file)],
                    check=True,
                    capture_output=True
                )
            elif system == "Linux":
                # Try different players
                for player in ["mpv", "mpg123", "ffplay", "aplay"]:
                    try:
                        if player == "ffplay":
                            subprocess.run(
                                [player, "-nodisp", "-autoexit", str(audio_file)],
                                check=True,
                                capture_output=True
                            )
                        else:
                            subprocess.run(
                                [player, str(audio_file)],
                                check=True,
                                capture_output=True
                            )
                        return
                    except FileNotFoundError:
                        continue
                raise TTSError("No audio player found. Install mpv, mpg123, or ffplay.")
            elif system == "Windows":
                # Use Windows Media Player via PowerShell
                subprocess.run(
                    ["powershell", "-c", f"(New-Object Media.SoundPlayer '{audio_file}').PlaySync()"],
                    check=True,
                    capture_output=True
                )
            else:
                raise TTSError(f"Unsupported platform: {system}")

        except subprocess.CalledProcessError as e:
            raise TTSError(f"Audio playback failed: {e}")
        except FileNotFoundError:
            raise TTSError("Audio player not found")

    def cleanup(self) -> None:
        """Clean up temporary files."""
        try:
            for f in self._temp_dir.glob("*.mp3"):
                f.unlink()
        except Exception:
            pass


# Global instance for convenience
_tts_instance = None


def get_tts() -> TextToSpeech:
    """Get global TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TextToSpeech()
    return _tts_instance


def speak(text: str) -> None:
    """Speak text using global TTS instance."""
    get_tts().speak(text)


def speak_slow(text: str) -> None:
    """Speak text slowly using global TTS instance."""
    get_tts().speak_slow(text)
