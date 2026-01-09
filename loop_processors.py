"""
Real-time Loop Processing Utilities

This module implements real audio processing algorithms for loop manipulation
including time-stretching, pitch-shifting, slicing, and crossfading.
"""

import numpy as np
from typing import List, Tuple, Optional
from scipy import signal
import logging

logger = logging.getLogger(__name__)


class TimeStretcher:
    """Phase vocoder-based time stretching without pitch change"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.frame_size = 2048
        self.hop_size = 512

    def stretch(self, audio: np.ndarray, stretch_factor: float) -> np.ndarray:
        """
        Time-stretch audio using phase vocoder

        Args:
            audio: Input audio signal
            stretch_factor: Stretch factor (0.5 = half speed, 2.0 = double speed)

        Returns:
            Time-stretched audio
        """
        if len(audio) == 0:
            return audio

        if stretch_factor == 1.0:
            return audio

        # Use overlap-add method for time stretching
        output_hop = int(self.hop_size * stretch_factor)

        # Apply STFT
        f, t, stft = signal.stft(
            audio,
            fs=self.sample_rate,
            window='hann',
            nperseg=self.frame_size,
            noverlap=self.frame_size - self.hop_size
        )

        # Phase vocoder processing
        num_frames = stft.shape[1]
        phase_advance = np.zeros((stft.shape[0], num_frames), dtype=complex)
        phase_advance[:, 0] = stft[:, 0]

        # Compute phase increment
        for i in range(1, num_frames):
            phase_diff = np.angle(stft[:, i]) - np.angle(stft[:, i-1])

            # Unwrap phase
            phase_diff = np.angle(np.exp(1j * phase_diff))

            # Compute instantaneous frequency
            inst_freq = phase_diff + 2 * np.pi * f / self.sample_rate * self.hop_size

            # Update phase
            phase = np.angle(phase_advance[:, i-1]) + inst_freq * stretch_factor
            magnitude = np.abs(stft[:, i])
            phase_advance[:, i] = magnitude * np.exp(1j * phase)

        # Inverse STFT with modified hop size
        _, stretched = signal.istft(
            phase_advance,
            fs=self.sample_rate,
            window='hann',
            nperseg=self.frame_size,
            noverlap=self.frame_size - output_hop
        )

        return stretched


class PitchShifter:
    """Pitch shifting using resampling and time-stretching"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.time_stretcher = TimeStretcher(sample_rate)

    def shift(self, audio: np.ndarray, semitones: float) -> np.ndarray:
        """
        Pitch-shift audio by semitones

        Args:
            audio: Input audio signal
            semitones: Number of semitones to shift (positive = up, negative = down)

        Returns:
            Pitch-shifted audio
        """
        if len(audio) == 0 or semitones == 0:
            return audio

        # Calculate pitch shift ratio
        pitch_ratio = 2 ** (semitones / 12.0)

        # Resample to change pitch
        num_samples = int(len(audio) / pitch_ratio)

        # Use linear interpolation for resampling
        original_indices = np.arange(len(audio))
        new_indices = np.linspace(0, len(audio) - 1, num_samples)
        resampled = np.interp(new_indices, original_indices, audio)

        # Time-stretch back to original length to maintain duration
        stretched = self.time_stretcher.stretch(resampled, pitch_ratio)

        # Trim or pad to match original length
        if len(stretched) > len(audio):
            return stretched[:len(audio)]
        elif len(stretched) < len(audio):
            return np.pad(stretched, (0, len(audio) - len(stretched)))
        return stretched


class LoopSlicer:
    """Loop slicing and rearrangement utilities"""

    @staticmethod
    def slice_by_beats(audio: np.ndarray, num_beats: int, bpm: float, sample_rate: int) -> List[np.ndarray]:
        """
        Slice loop into beat-aligned segments

        Args:
            audio: Input loop audio
            num_beats: Number of beats in the loop
            bpm: Tempo in beats per minute
            sample_rate: Audio sample rate

        Returns:
            List of audio slices (one per beat)
        """
        if len(audio) == 0 or num_beats == 0:
            return []

        # Calculate samples per beat
        beat_duration_sec = 60.0 / bpm
        samples_per_beat = int(beat_duration_sec * sample_rate)

        # Slice loop
        slices = []
        for i in range(num_beats):
            start = i * samples_per_beat
            end = min((i + 1) * samples_per_beat, len(audio))

            if start < len(audio):
                slices.append(audio[start:end])

        return slices

    @staticmethod
    def slice_by_transients(audio: np.ndarray, sample_rate: int, threshold: float = 0.3) -> List[Tuple[int, int]]:
        """
        Detect transients and return slice points

        Args:
            audio: Input audio
            sample_rate: Audio sample rate
            threshold: Transient detection threshold (0.0 to 1.0)

        Returns:
            List of (start, end) sample indices for each slice
        """
        if len(audio) == 0:
            return []

        # Calculate onset strength envelope
        hop_length = 512
        onset_env = np.abs(np.diff(audio, prepend=0))

        # Smooth with moving average
        window_size = int(sample_rate * 0.02)  # 20ms window
        if window_size > len(onset_env):
            window_size = len(onset_env)

        onset_smooth = np.convolve(onset_env, np.ones(window_size)/window_size, mode='same')

        # Normalize
        max_onset = np.max(onset_smooth)
        if max_onset > 0:
            onset_smooth /= max_onset

        # Find peaks above threshold
        peaks = []
        for i in range(1, len(onset_smooth) - 1):
            if (onset_smooth[i] > threshold and
                onset_smooth[i] > onset_smooth[i-1] and
                onset_smooth[i] > onset_smooth[i+1]):
                peaks.append(i)

        # Create slices
        if len(peaks) == 0:
            return [(0, len(audio))]

        slices = []
        for i in range(len(peaks)):
            start = peaks[i]
            end = peaks[i + 1] if i + 1 < len(peaks) else len(audio)
            slices.append((start, end))

        return slices

    @staticmethod
    def rearrange_slices(slices: List[np.ndarray], pattern: List[int]) -> np.ndarray:
        """
        Rearrange slices according to pattern

        Args:
            slices: List of audio slices
            pattern: Slice indices in desired order (e.g., [0, 2, 1, 3])

        Returns:
            Rearranged audio
        """
        if not slices or not pattern:
            return np.array([])

        rearranged = []
        for idx in pattern:
            if 0 <= idx < len(slices):
                rearranged.append(slices[idx])

        if rearranged:
            return np.concatenate(rearranged)
        return np.array([])


class CrossfadeProcessor:
    """Crossfading utilities for smooth loop transitions"""

    @staticmethod
    def crossfade(audio1: np.ndarray, audio2: np.ndarray, crossfade_samples: int) -> np.ndarray:
        """
        Crossfade between two audio segments

        Args:
            audio1: First audio segment (fades out)
            audio2: Second audio segment (fades in)
            crossfade_samples: Length of crossfade in samples

        Returns:
            Crossfaded audio
        """
        if len(audio1) == 0:
            return audio2
        if len(audio2) == 0:
            return audio1

        # Limit crossfade length
        crossfade_samples = min(crossfade_samples, len(audio1), len(audio2))

        if crossfade_samples == 0:
            return np.concatenate([audio1, audio2])

        # Create fade curves (equal power crossfade)
        fade_out = np.cos(np.linspace(0, np.pi/2, crossfade_samples)) ** 2
        fade_in = np.sin(np.linspace(0, np.pi/2, crossfade_samples)) ** 2

        # Apply crossfade
        crossfaded_section = (
            audio1[-crossfade_samples:] * fade_out +
            audio2[:crossfade_samples] * fade_in
        )

        # Combine segments
        result = np.concatenate([
            audio1[:-crossfade_samples],
            crossfaded_section,
            audio2[crossfade_samples:]
        ])

        return result

    @staticmethod
    def loop_crossfade(audio: np.ndarray, crossfade_samples: int) -> np.ndarray:
        """
        Apply crossfade to make loop seamless

        Args:
            audio: Loop audio
            crossfade_samples: Length of crossfade in samples

        Returns:
            Seamless loop with crossfade
        """
        if len(audio) < crossfade_samples * 2:
            return audio

        # Equal power crossfade between end and beginning
        fade_out = np.cos(np.linspace(0, np.pi/2, crossfade_samples)) ** 2
        fade_in = np.sin(np.linspace(0, np.pi/2, crossfade_samples)) ** 2

        # Crossfade end with beginning
        audio[-crossfade_samples:] = (
            audio[-crossfade_samples:] * fade_out +
            audio[:crossfade_samples] * fade_in
        )

        return audio


class LoopQuantizer:
    """Loop length quantization to beat grid"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.time_stretcher = TimeStretcher(sample_rate)

    def quantize_to_beats(self, audio: np.ndarray, target_beats: int, bpm: float) -> np.ndarray:
        """
        Quantize loop length to exact number of beats

        Args:
            audio: Input loop audio
            target_beats: Target number of beats
            bpm: Tempo in beats per minute

        Returns:
            Quantized loop
        """
        if len(audio) == 0:
            return audio

        # Calculate target length in samples
        beat_duration_sec = 60.0 / bpm
        target_length_sec = beat_duration_sec * target_beats
        target_samples = int(target_length_sec * self.sample_rate)

        # Calculate stretch factor
        stretch_factor = target_samples / len(audio)

        # Time-stretch to exact length
        quantized = self.time_stretcher.stretch(audio, stretch_factor)

        # Trim or pad to exact length
        if len(quantized) > target_samples:
            return quantized[:target_samples]
        elif len(quantized) < target_samples:
            return np.pad(quantized, (0, target_samples - len(quantized)))

        return quantized

    def snap_to_grid(self, current_position: int, grid_size: int) -> int:
        """
        Snap playback position to nearest grid point

        Args:
            current_position: Current position in samples
            grid_size: Grid size in samples

        Returns:
            Snapped position
        """
        if grid_size == 0:
            return current_position

        return (current_position // grid_size) * grid_size


class LoopRecorder:
    """Real-time loop recording with buffer management"""

    def __init__(self, sample_rate: int = 44100, max_length_seconds: float = 300.0):
        self.sample_rate = sample_rate
        self.max_samples = int(max_length_seconds * sample_rate)
        self.recording_buffer: List[np.ndarray] = []
        self.is_recording = False

    def start_recording(self):
        """Start recording"""
        self.recording_buffer = []
        self.is_recording = True

    def add_buffer(self, audio_buffer: np.ndarray):
        """Add audio buffer to recording"""
        if not self.is_recording:
            return

        self.recording_buffer.append(audio_buffer.copy())

        # Check max length
        total_samples = sum(len(buf) for buf in self.recording_buffer)
        if total_samples >= self.max_samples:
            self.stop_recording()

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return recorded audio"""
        self.is_recording = False

        if not self.recording_buffer:
            return np.array([])

        # Concatenate all buffers
        recorded = np.concatenate(self.recording_buffer)

        # Trim to max length
        if len(recorded) > self.max_samples:
            recorded = recorded[:self.max_samples]

        return recorded

    def get_recorded_length_seconds(self) -> float:
        """Get current recording length in seconds"""
        if not self.recording_buffer:
            return 0.0

        total_samples = sum(len(buf) for buf in self.recording_buffer)
        return total_samples / self.sample_rate


class OverdubProcessor:
    """Overdub processing with mixing"""

    @staticmethod
    def overdub(original: np.ndarray, new_audio: np.ndarray, mix: float = 0.5) -> np.ndarray:
        """
        Mix new audio over original (overdubbing)

        Args:
            original: Original loop audio
            new_audio: New audio to overdub
            mix: Mix amount (0.0 = all original, 1.0 = all new)

        Returns:
            Mixed audio
        """
        if len(original) == 0:
            return new_audio
        if len(new_audio) == 0:
            return original

        # Ensure same length
        max_len = max(len(original), len(new_audio))

        if len(original) < max_len:
            original = np.pad(original, (0, max_len - len(original)))
        if len(new_audio) < max_len:
            new_audio = np.pad(new_audio, (0, max_len - len(new_audio)))

        # Mix with specified ratio
        overdubbed = original * (1 - mix) + new_audio * mix

        # Normalize to prevent clipping
        peak = np.max(np.abs(overdubbed))
        if peak > 0.95:
            overdubbed = overdubbed / peak * 0.95

        return overdubbed

    @staticmethod
    def multiply(original: np.ndarray, repeat_count: int) -> np.ndarray:
        """
        Multiply loop length by repeating

        Args:
            original: Original loop
            repeat_count: Number of times to repeat

        Returns:
            Multiplied loop
        """
        if len(original) == 0 or repeat_count <= 1:
            return original

        return np.tile(original, repeat_count)
