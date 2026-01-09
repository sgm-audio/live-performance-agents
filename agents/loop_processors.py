"""
Loop processing utilities for LiveLoopingAgent

Production-quality time-stretching and pitch-shifting implementations.
"""

import numpy as np
from typing import Dict, Any, Optional
from scipy import signal

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    import logging
    logging.warning("librosa not available - using basic time/pitch algorithms")


class TimeStretcher:
    """
    Time-stretching processor using phase vocoder

    Stretches audio duration without changing pitch.
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def process(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """
        Time-stretch audio by factor using phase vocoder

        Args:
            audio: Audio data (num_samples,) or (num_samples, num_channels)
            factor: Stretch factor (2.0 = twice as long, 0.5 = half as long)

        Returns:
            Time-stretched audio with same pitch
        """
        if factor <= 0:
            raise ValueError("Stretch factor must be positive")

        if abs(factor - 1.0) < 0.01:
            return audio.copy()  # No stretching needed

        if LIBROSA_AVAILABLE:
            return self._stretch_librosa(audio, factor)
        else:
            return self._stretch_basic(audio, factor)

    def _stretch_librosa(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """High-quality time stretching with librosa"""
        is_stereo = len(audio.shape) > 1 and audio.shape[1] > 1

        if is_stereo:
            # Process each channel separately
            stretched_channels = []
            for ch in range(audio.shape[1]):
                stretched = librosa.effects.time_stretch(
                    audio[:, ch].astype(np.float32),
                    rate=1.0 / factor  # librosa uses rate (inverse of factor)
                )
                stretched_channels.append(stretched)
            return np.column_stack(stretched_channels)
        else:
            # Mono
            audio_mono = audio if len(audio.shape) == 1 else audio[:, 0]
            stretched = librosa.effects.time_stretch(
                audio_mono.astype(np.float32),
                rate=1.0 / factor
            )
            return stretched if len(audio.shape) == 1 else stretched.reshape(-1, 1)

    def _stretch_basic(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """Basic time stretching using overlap-add (fallback)"""
        # Simple overlap-add method
        hop_size = 512
        window_size = 2048

        is_stereo = len(audio.shape) > 1 and audio.shape[1] > 1
        audio_mono = audio if len(audio.shape) == 1 else audio.mean(axis=1)

        # Calculate output length
        target_length = int(len(audio_mono) * factor)
        stretched = np.zeros(target_length, dtype=np.float32)

        # Window function
        window = np.hanning(window_size)

        # Overlap-add with time scaling
        input_hop = int(hop_size / factor)
        output_pos = 0
        input_pos = 0

        while input_pos + window_size < len(audio_mono) and output_pos + window_size < target_length:
            # Extract windowed segment
            segment = audio_mono[input_pos:input_pos + window_size] * window

            # Add to output
            stretched[output_pos:output_pos + window_size] += segment

            input_pos += input_hop
            output_pos += hop_size

        # Restore stereo if needed
        if is_stereo:
            return np.column_stack([stretched, stretched])
        return stretched if len(audio.shape) == 1 else stretched.reshape(-1, 1)


class PitchShifter:
    """
    Pitch-shifting processor

    Changes pitch without affecting duration.
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.time_stretcher = TimeStretcher(sample_rate)

    def process(self, audio: np.ndarray, semitones: float) -> np.ndarray:
        """
        Pitch-shift audio by semitones without changing duration

        Args:
            audio: Audio data (num_samples,) or (num_samples, num_channels)
            semitones: Pitch shift in semitones (12 = 1 octave up, -12 = 1 octave down)

        Returns:
            Pitch-shifted audio with same duration
        """
        if abs(semitones) < 0.01:
            return audio.copy()  # No shift needed

        if LIBROSA_AVAILABLE:
            return self._shift_librosa(audio, semitones)
        else:
            return self._shift_basic(audio, semitones)

    def _shift_librosa(self, audio: np.ndarray, semitones: float) -> np.ndarray:
        """High-quality pitch shifting with librosa"""
        is_stereo = len(audio.shape) > 1 and audio.shape[1] > 1

        if is_stereo:
            # Process each channel separately
            shifted_channels = []
            for ch in range(audio.shape[1]):
                shifted = librosa.effects.pitch_shift(
                    audio[:, ch].astype(np.float32),
                    sr=self.sample_rate,
                    n_steps=semitones
                )
                shifted_channels.append(shifted)
            return np.column_stack(shifted_channels)
        else:
            # Mono
            audio_mono = audio if len(audio.shape) == 1 else audio[:, 0]
            shifted = librosa.effects.pitch_shift(
                audio_mono.astype(np.float32),
                sr=self.sample_rate,
                n_steps=semitones
            )
            return shifted if len(audio.shape) == 1 else shifted.reshape(-1, 1)

    def _shift_basic(self, audio: np.ndarray, semitones: float) -> np.ndarray:
        """Basic pitch shifting using time-stretch + resample (fallback)"""
        # Calculate pitch shift ratio
        ratio = 2.0 ** (semitones / 12.0)

        # Step 1: Resample to change pitch (also changes duration)
        is_stereo = len(audio.shape) > 1 and audio.shape[1] > 1
        original_length = len(audio)

        if is_stereo:
            # Resample each channel
            resampled_channels = []
            for ch in range(audio.shape[1]):
                resampled = signal.resample(audio[:, ch], int(len(audio) / ratio))
                resampled_channels.append(resampled)
            resampled = np.column_stack(resampled_channels)
        else:
            audio_mono = audio if len(audio.shape) == 1 else audio[:, 0]
            resampled = signal.resample(audio_mono, int(len(audio_mono) / ratio))
            if len(audio.shape) > 1:
                resampled = resampled.reshape(-1, 1)

        # Step 2: Time-stretch back to original duration (without changing pitch)
        # This compensates for the duration change from resampling
        duration_ratio = original_length / len(resampled)
        result = self.time_stretcher.process(resampled, duration_ratio)

        # Ensure exact length match
        if len(result) > original_length:
            result = result[:original_length]
        elif len(result) < original_length:
            if is_stereo:
                padding = np.zeros((original_length - len(result), result.shape[1]))
            else:
                padding = np.zeros((original_length - len(result),) + result.shape[1:])
            result = np.concatenate([result, padding])

        return result


class LoopSlicer:
    """Loop slicing and rearrangement processor (placeholder)"""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def slice_loop(self, audio: np.ndarray, num_slices: int) -> list:
        """Slice loop into equal parts"""
        slice_length = len(audio) // num_slices
        return [audio[i * slice_length:(i + 1) * slice_length] for i in range(num_slices)]

    def rearrange(self, slices: list, pattern: list) -> np.ndarray:
        """Rearrange slices according to pattern"""
        return np.concatenate([slices[i] for i in pattern])


class CrossfadeProcessor:
    """Crossfade processor for seamless loop transitions"""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def crossfade(self, audio_a: np.ndarray, audio_b: np.ndarray,
                  crossfade_ms: float = 10.0) -> np.ndarray:
        """
        Crossfade between two audio buffers

        Args:
            audio_a: First audio buffer
            audio_b: Second audio buffer
            crossfade_ms: Crossfade time in milliseconds

        Returns:
            Crossfaded audio
        """
        crossfade_samples = int((crossfade_ms / 1000.0) * self.sample_rate)
        crossfade_samples = min(crossfade_samples, len(audio_a), len(audio_b))

        if crossfade_samples == 0:
            return audio_a

        # Create crossfade envelope
        fade_out = np.linspace(1.0, 0.0, crossfade_samples)
        fade_in = np.linspace(0.0, 1.0, crossfade_samples)

        # Apply crossfade
        result = audio_a.copy()
        if len(audio_a.shape) > 1:  # Stereo
            for ch in range(audio_a.shape[1]):
                result[-crossfade_samples:, ch] = (
                    audio_a[-crossfade_samples:, ch] * fade_out +
                    audio_b[:crossfade_samples, ch] * fade_in
                )
        else:  # Mono
            result[-crossfade_samples:] = (
                audio_a[-crossfade_samples:] * fade_out +
                audio_b[:crossfade_samples] * fade_in
            )

        return result


class LoopQuantizer:
    """Quantize loop start/stop to beat grid"""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def quantize_to_beat(self, sample_position: int, bpm: float,
                        beats_per_bar: int = 4) -> int:
        """
        Quantize sample position to nearest beat

        Args:
            sample_position: Position in samples
            bpm: Tempo in beats per minute
            beats_per_bar: Time signature numerator

        Returns:
            Quantized sample position
        """
        samples_per_beat = (60.0 / bpm) * self.sample_rate
        beat_number = round(sample_position / samples_per_beat)
        return int(beat_number * samples_per_beat)


class LoopRecorder:
    """Real-time loop recording with auto-length detection"""

    def __init__(self, sample_rate: int = 48000, max_length_seconds: float = 60.0):
        self.sample_rate = sample_rate
        self.max_length_samples = int(max_length_seconds * sample_rate)
        self.buffer = None
        self.position = 0
        self.is_recording = False

    def start_recording(self, num_channels: int = 2):
        """Start recording"""
        self.buffer = np.zeros((self.max_length_samples, num_channels), dtype=np.float32)
        self.position = 0
        self.is_recording = True

    def record_chunk(self, audio: np.ndarray):
        """Record audio chunk"""
        if not self.is_recording or self.buffer is None:
            return

        chunk_length = len(audio)
        if self.position + chunk_length > self.max_length_samples:
            # Hit max length
            remaining = self.max_length_samples - self.position
            self.buffer[self.position:self.position + remaining] = audio[:remaining]
            self.position = self.max_length_samples
            self.is_recording = False
        else:
            self.buffer[self.position:self.position + chunk_length] = audio
            self.position += chunk_length

    def stop_recording(self) -> Optional[np.ndarray]:
        """Stop recording and return recorded audio"""
        if self.buffer is None:
            return None

        self.is_recording = False
        recorded = self.buffer[:self.position].copy()
        self.buffer = None
        self.position = 0
        return recorded


class OverdubProcessor:
    """Overdub processor for layering audio"""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def overdub(self, existing: np.ndarray, new_audio: np.ndarray,
                mix: float = 0.5) -> np.ndarray:
        """
        Overdub new audio onto existing loop

        Args:
            existing: Existing loop audio
            new_audio: New audio to overdub
            mix: Mix amount (0.0 = all existing, 1.0 = all new, 0.5 = equal mix)

        Returns:
            Mixed audio
        """
        # Ensure same length
        min_length = min(len(existing), len(new_audio))

        if len(existing.shape) > 1:  # Stereo
            result = existing[:min_length].copy()
            result = result * (1.0 - mix) + new_audio[:min_length] * mix
        else:  # Mono
            result = existing[:min_length] * (1.0 - mix) + new_audio[:min_length] * mix

        return result
