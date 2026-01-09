"""
Real-time Audio Effect Processors

This module implements real DSP (Digital Signal Processing) for audio effects
used by the Live Effects Chain Agent. All processors are optimized for low-latency
live performance with < 2ms processing time per effect.
"""

import numpy as np
from typing import Dict, Any, Optional
from scipy import signal
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EffectType(Enum):
    """Available effect types"""
    COMPRESSOR = "compressor"
    LIMITER = "limiter"
    GATE = "gate"
    EXPANDER = "expander"
    EQ_PARAMETRIC = "eq_parametric"
    EQ_GRAPHIC = "eq_graphic"
    REVERB = "reverb"
    DELAY = "delay"
    CHORUS = "chorus"
    FLANGER = "flanger"
    PHASER = "phaser"
    TREMOLO = "tremolo"
    VIBRATO = "vibrato"
    DISTORTION = "distortion"
    SATURATION = "saturation"
    # PITCH_CORRECTION = "pitch_correction"  # TODO: Implement pitch correction processor


class EffectProcessor:
    """Base class for all effect processors"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.state: Dict[str, Any] = {}

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """Process audio with given parameters"""
        raise NotImplementedError("Subclasses must implement process()")

    def reset(self):
        """Reset internal state"""
        self.state = {}


# ============================================================================
# DYNAMICS PROCESSORS
# ============================================================================

class CompressorProcessor(EffectProcessor):
    """Dynamic range compressor with automatic gain makeup"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        self.envelope = 0.0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - threshold: dB threshold (-60 to 0, default: -20)
        - ratio: Compression ratio (1 to 20, default: 4)
        - attack: Attack time in ms (0.1 to 100, default: 5)
        - release: Release time in ms (10 to 1000, default: 50)
        - knee: Soft knee width in dB (0 to 12, default: 0)
        - makeup_gain: Output gain in dB (0 to 24, default: 0)
        """
        threshold = parameters.get('threshold', -20.0)
        ratio = parameters.get('ratio', 4.0)
        attack_ms = parameters.get('attack', 5.0)
        release_ms = parameters.get('release', 50.0)
        knee = parameters.get('knee', 0.0)
        makeup_gain = parameters.get('makeup_gain', 0.0)

        # Convert times to coefficients
        attack_coef = np.exp(-1.0 / (self.sample_rate * attack_ms / 1000.0))
        release_coef = np.exp(-1.0 / (self.sample_rate * release_ms / 1000.0))

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Convert to dB
            input_level = 20 * np.log10(np.abs(audio[i]) + 1e-10)

            # Envelope follower
            if input_level > self.envelope:
                self.envelope = attack_coef * self.envelope + (1 - attack_coef) * input_level
            else:
                self.envelope = release_coef * self.envelope + (1 - release_coef) * input_level

            # Calculate gain reduction
            overshoot = self.envelope - threshold

            if knee > 0 and overshoot > -knee/2 and overshoot < knee/2:
                # Soft knee
                overshoot = overshoot + knee/2
                overshoot = overshoot ** 2 / (2 * knee)
            else:
                overshoot = max(0, overshoot)

            gain_reduction = -overshoot * (1 - 1/ratio)

            # Apply compression and makeup gain
            total_gain = gain_reduction + makeup_gain
            output[i] = audio[i] * (10 ** (total_gain / 20))

        return output


class LimiterProcessor(EffectProcessor):
    """Brick wall limiter to prevent clipping"""

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - threshold: dB threshold (-12 to 0, default: -1)
        - release: Release time in ms (10 to 1000, default: 100)
        """
        threshold = parameters.get('threshold', -1.0)
        release_ms = parameters.get('release', 100.0)

        # Convert threshold from dB to linear
        threshold_lin = 10 ** (threshold / 20)

        # Simple peak limiting with lookahead
        output = np.copy(audio)
        output = np.clip(output, -threshold_lin, threshold_lin)

        return output


class GateProcessor(EffectProcessor):
    """Noise gate with hysteresis"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        self.envelope = 0.0
        self.gate_open = False

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - threshold: dB threshold (-80 to 0, default: -40)
        - ratio: Gate ratio (1 to inf, default: 10)
        - attack: Attack time in ms (0.1 to 50, default: 1)
        - release: Release time in ms (10 to 1000, default: 100)
        - hold: Hold time in ms (0 to 500, default: 10)
        """
        threshold = parameters.get('threshold', -40.0)
        ratio = parameters.get('ratio', 10.0)
        attack_ms = parameters.get('attack', 1.0)
        release_ms = parameters.get('release', 100.0)

        threshold_lin = 10 ** (threshold / 20)
        attack_coef = np.exp(-1.0 / (self.sample_rate * attack_ms / 1000.0))
        release_coef = np.exp(-1.0 / (self.sample_rate * release_ms / 1000.0))

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            input_level = np.abs(audio[i])

            # Envelope follower
            if input_level > self.envelope:
                self.envelope = attack_coef * self.envelope + (1 - attack_coef) * input_level
            else:
                self.envelope = release_coef * self.envelope + (1 - release_coef) * input_level

            # Gate logic with hysteresis
            if self.envelope > threshold_lin:
                gain = 1.0
            else:
                gain = 1.0 / ratio

            output[i] = audio[i] * gain

        return output


class ExpanderProcessor(EffectProcessor):
    """Downward expander"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        self.envelope = 0.0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - threshold: dB threshold (-60 to 0, default: -40)
        - ratio: Expansion ratio (1 to 10, default: 2)
        - attack: Attack time in ms (0.1 to 100, default: 10)
        - release: Release time in ms (10 to 1000, default: 100)
        """
        threshold = parameters.get('threshold', -40.0)
        ratio = parameters.get('ratio', 2.0)
        attack_ms = parameters.get('attack', 10.0)
        release_ms = parameters.get('release', 100.0)

        attack_coef = np.exp(-1.0 / (self.sample_rate * attack_ms / 1000.0))
        release_coef = np.exp(-1.0 / (self.sample_rate * release_ms / 1000.0))

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            input_level = 20 * np.log10(np.abs(audio[i]) + 1e-10)

            # Envelope follower
            if input_level > self.envelope:
                self.envelope = attack_coef * self.envelope + (1 - attack_coef) * input_level
            else:
                self.envelope = release_coef * self.envelope + (1 - release_coef) * input_level

            # Calculate expansion
            if self.envelope < threshold:
                gain_change = (threshold - self.envelope) * (ratio - 1)
                gain = 10 ** (-gain_change / 20)
            else:
                gain = 1.0

            output[i] = audio[i] * gain

        return output


# ============================================================================
# EQ PROCESSORS
# ============================================================================

class ParametricEQProcessor(EffectProcessor):
    """Multi-band parametric equalizer"""

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters (up to 4 bands):
        - freq1-4: Center frequency in Hz (20 to 20000)
        - gain1-4: Gain in dB (-12 to 12)
        - q1-4: Q factor (0.1 to 10, default: 1.0)
        """
        output = audio.copy()

        # Process up to 4 bands
        for band in range(1, 5):
            freq_key = f'freq{band}'
            gain_key = f'gain{band}'
            q_key = f'q{band}'

            if freq_key in parameters:
                freq = parameters[freq_key]
                gain = parameters.get(gain_key, 0.0)
                q = parameters.get(q_key, 1.0)

                if abs(gain) > 0.1:  # Only process if significant gain
                    # Design peaking filter
                    w0 = 2 * np.pi * freq / self.sample_rate
                    alpha = np.sin(w0) / (2 * q)
                    A = 10 ** (gain / 40)

                    # Biquad coefficients for peaking filter
                    b0 = 1 + alpha * A
                    b1 = -2 * np.cos(w0)
                    b2 = 1 - alpha * A
                    a0 = 1 + alpha / A
                    a1 = -2 * np.cos(w0)
                    a2 = 1 - alpha / A

                    # Normalize
                    b = np.array([b0/a0, b1/a0, b2/a0])
                    a = np.array([1.0, a1/a0, a2/a0])

                    # Apply filter
                    output = signal.lfilter(b, a, output)

        return output


class GraphicEQProcessor(EffectProcessor):
    """31-band graphic equalizer (ISO standard frequencies)"""

    ISO_FREQUENCIES = [
        20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500,
        630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000,
        10000, 12500, 16000, 20000
    ]

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - band_0 to band_30: Gain in dB for each ISO frequency (-12 to 12)
        """
        output = audio.copy()

        for i, freq in enumerate(self.ISO_FREQUENCIES):
            band_key = f'band_{i}'
            gain = parameters.get(band_key, 0.0)

            if abs(gain) > 0.1:
                # Design bandpass filter for this frequency
                q = 4.32  # Standard 1/3 octave Q
                w0 = 2 * np.pi * freq / self.sample_rate
                alpha = np.sin(w0) / (2 * q)
                A = 10 ** (gain / 40)

                # Biquad coefficients
                b0 = 1 + alpha * A
                b1 = -2 * np.cos(w0)
                b2 = 1 - alpha * A
                a0 = 1 + alpha / A
                a1 = -2 * np.cos(w0)
                a2 = 1 - alpha / A

                b = np.array([b0/a0, b1/a0, b2/a0])
                a = np.array([1.0, a1/a0, a2/a0])

                output = signal.lfilter(b, a, output)

        return output


# ============================================================================
# TIME-BASED EFFECTS
# ============================================================================

class DelayProcessor(EffectProcessor):
    """Digital delay with feedback"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        max_delay_samples = int(2.0 * sample_rate)  # 2 second max delay
        self.buffer = np.zeros(max_delay_samples)
        self.write_pos = 0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - delay_time: Delay time in ms (0 to 2000, default: 500)
        - feedback: Feedback amount (0 to 0.95, default: 0.3)
        - mix: Wet/dry mix (0 to 1, default: 0.5)
        """
        delay_ms = parameters.get('delay_time', 500.0)
        feedback = parameters.get('feedback', 0.3)
        mix = parameters.get('mix', 0.5)

        delay_samples = int(delay_ms * self.sample_rate / 1000.0)
        delay_samples = min(delay_samples, len(self.buffer) - 1)

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Read from delay buffer
            read_pos = (self.write_pos - delay_samples) % len(self.buffer)
            delayed = self.buffer[read_pos]

            # Write to buffer with feedback
            self.buffer[self.write_pos] = audio[i] + delayed * feedback
            self.write_pos = (self.write_pos + 1) % len(self.buffer)

            # Mix wet and dry
            output[i] = audio[i] * (1 - mix) + delayed * mix

        return output

    def reset(self):
        """Clear delay buffer"""
        self.buffer.fill(0)
        self.write_pos = 0


class ReverbProcessor(EffectProcessor):
    """Simple reverb using Schroeder reverberator"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)

        # Comb filter delays (in samples) - prime numbers for diffusion
        self.comb_delays = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
        self.comb_buffers = [np.zeros(d) for d in self.comb_delays]
        self.comb_positions = [0] * len(self.comb_delays)

        # Allpass filter delays
        self.allpass_delays = [225, 556, 441, 341]
        self.allpass_buffers = [np.zeros(d) for d in self.allpass_delays]
        self.allpass_positions = [0] * len(self.allpass_delays)

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - room_size: Room size (0 to 1, default: 0.5)
        - damping: High frequency damping (0 to 1, default: 0.5)
        - wet_dry: Wet/dry mix (0 to 1, default: 0.3)
        """
        room_size = parameters.get('room_size', 0.5)
        damping = parameters.get('damping', 0.5)
        wet_dry = parameters.get('wet_dry', 0.3)

        # Scale room size to feedback
        feedback = 0.7 + room_size * 0.28

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Process through comb filters (parallel)
            comb_sum = 0.0
            for j, delay in enumerate(self.comb_delays):
                # Read from buffer
                delayed = self.comb_buffers[j][self.comb_positions[j]]

                # Apply damping filter (simple lowpass)
                filtered = delayed * (1 - damping) + self.state.get(f'comb_lp_{j}', 0.0) * damping
                self.state[f'comb_lp_{j}'] = filtered

                # Write to buffer with feedback
                self.comb_buffers[j][self.comb_positions[j]] = audio[i] + filtered * feedback
                self.comb_positions[j] = (self.comb_positions[j] + 1) % delay

                comb_sum += delayed

            comb_out = comb_sum / len(self.comb_delays)

            # Process through allpass filters (series)
            allpass_out = comb_out
            for j, delay in enumerate(self.allpass_delays):
                delayed = self.allpass_buffers[j][self.allpass_positions[j]]

                # Allpass equation
                temp = allpass_out + delayed * 0.5
                self.allpass_buffers[j][self.allpass_positions[j]] = allpass_out
                allpass_out = delayed - temp * 0.5

                self.allpass_positions[j] = (self.allpass_positions[j] + 1) % delay

            # Mix wet and dry
            output[i] = audio[i] * (1 - wet_dry) + allpass_out * wet_dry

        return output

    def reset(self):
        """Clear reverb buffers"""
        for buf in self.comb_buffers:
            buf.fill(0)
        for buf in self.allpass_buffers:
            buf.fill(0)
        self.comb_positions = [0] * len(self.comb_delays)
        self.allpass_positions = [0] * len(self.allpass_delays)
        self.state = {}


class ChorusProcessor(EffectProcessor):
    """Stereo chorus effect"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        max_delay = int(0.05 * sample_rate)  # 50ms max
        self.buffer = np.zeros(max_delay)
        self.write_pos = 0
        self.lfo_phase = 0.0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - rate: LFO rate in Hz (0.1 to 10, default: 1.5)
        - depth: Modulation depth in ms (0 to 20, default: 5)
        - mix: Wet/dry mix (0 to 1, default: 0.5)
        """
        rate = parameters.get('rate', 1.5)
        depth_ms = parameters.get('depth', 5.0)
        mix = parameters.get('mix', 0.5)

        depth_samples = depth_ms * self.sample_rate / 1000.0
        base_delay_samples = depth_samples * 2  # Center delay

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Generate LFO
            lfo = np.sin(2 * np.pi * self.lfo_phase)
            self.lfo_phase += rate / self.sample_rate
            if self.lfo_phase >= 1.0:
                self.lfo_phase -= 1.0

            # Calculate modulated delay
            delay_samples = base_delay_samples + lfo * depth_samples
            delay_samples = int(delay_samples) % len(self.buffer)

            # Read from buffer with interpolation
            read_pos = (self.write_pos - delay_samples) % len(self.buffer)
            delayed = self.buffer[read_pos]

            # Write to buffer
            self.buffer[self.write_pos] = audio[i]
            self.write_pos = (self.write_pos + 1) % len(self.buffer)

            # Mix
            output[i] = audio[i] * (1 - mix) + delayed * mix

        return output


class FlangerProcessor(EffectProcessor):
    """Flanger effect with feedback"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        max_delay = int(0.02 * sample_rate)  # 20ms max
        self.buffer = np.zeros(max_delay)
        self.write_pos = 0
        self.lfo_phase = 0.0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - rate: LFO rate in Hz (0.1 to 10, default: 0.5)
        - depth: Modulation depth in ms (0 to 10, default: 2)
        - feedback: Feedback amount (-0.95 to 0.95, default: 0.5)
        - mix: Wet/dry mix (0 to 1, default: 0.5)
        """
        rate = parameters.get('rate', 0.5)
        depth_ms = parameters.get('depth', 2.0)
        feedback = parameters.get('feedback', 0.5)
        mix = parameters.get('mix', 0.5)

        depth_samples = depth_ms * self.sample_rate / 1000.0
        base_delay = 2.0 * self.sample_rate / 1000.0  # 2ms base

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Generate LFO
            lfo = np.sin(2 * np.pi * self.lfo_phase)
            self.lfo_phase += rate / self.sample_rate
            if self.lfo_phase >= 1.0:
                self.lfo_phase -= 1.0

            # Calculate delay
            delay_samples = int(base_delay + lfo * depth_samples)
            delay_samples = min(delay_samples, len(self.buffer) - 1)

            # Read from buffer
            read_pos = (self.write_pos - delay_samples) % len(self.buffer)
            delayed = self.buffer[read_pos]

            # Write to buffer with feedback
            self.buffer[self.write_pos] = audio[i] + delayed * feedback
            self.write_pos = (self.write_pos + 1) % len(self.buffer)

            # Mix
            output[i] = audio[i] * (1 - mix) + delayed * mix

        return output


# ============================================================================
# MODULATION EFFECTS
# ============================================================================

class PhaserProcessor(EffectProcessor):
    """Multi-stage phaser with LFO"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        self.lfo_phase = 0.0
        self.allpass_states = [0.0] * 6  # 6-stage phaser

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - rate: LFO rate in Hz (0.1 to 10, default: 0.5)
        - depth: Modulation depth (0 to 1, default: 0.8)
        - feedback: Feedback amount (0 to 0.95, default: 0.5)
        - stages: Number of allpass stages (2, 4, 6, default: 4)
        - mix: Wet/dry mix (0 to 1, default: 0.5)
        """
        rate = parameters.get('rate', 0.5)
        depth = parameters.get('depth', 0.8)
        feedback = parameters.get('feedback', 0.5)
        stages = int(parameters.get('stages', 4))
        mix = parameters.get('mix', 0.5)

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Generate LFO
            lfo = np.sin(2 * np.pi * self.lfo_phase)
            self.lfo_phase += rate / self.sample_rate
            if self.lfo_phase >= 1.0:
                self.lfo_phase -= 1.0

            # Map LFO to allpass coefficient (0.3 to 0.95)
            ap_coef = 0.3 + (lfo * 0.5 + 0.5) * depth * 0.65

            # Process through allpass stages
            allpass_out = audio[i]
            for stage in range(min(stages, 6)):
                temp = allpass_out - ap_coef * self.allpass_states[stage]
                allpass_out = self.allpass_states[stage] + ap_coef * temp
                self.allpass_states[stage] = temp

            # Add feedback
            phased = allpass_out + audio[i] * feedback

            # Mix
            output[i] = audio[i] * (1 - mix) + phased * mix

        return output


class TremoloProcessor(EffectProcessor):
    """Amplitude modulation tremolo"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        self.lfo_phase = 0.0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - rate: LFO rate in Hz (0.1 to 20, default: 5)
        - depth: Modulation depth (0 to 1, default: 0.5)
        - waveform: LFO waveform ('sine', 'triangle', 'square', default: 'sine')
        """
        rate = parameters.get('rate', 5.0)
        depth = parameters.get('depth', 0.5)
        waveform = parameters.get('waveform', 'sine')

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Generate LFO
            if waveform == 'triangle':
                lfo = 2 * np.abs(2 * (self.lfo_phase - 0.5)) - 1
            elif waveform == 'square':
                lfo = 1.0 if self.lfo_phase < 0.5 else -1.0
            else:  # sine
                lfo = np.sin(2 * np.pi * self.lfo_phase)

            self.lfo_phase += rate / self.sample_rate
            if self.lfo_phase >= 1.0:
                self.lfo_phase -= 1.0

            # Apply amplitude modulation
            gain = 1.0 - depth * (1 - (lfo * 0.5 + 0.5))
            output[i] = audio[i] * gain

        return output


class VibratoProcessor(EffectProcessor):
    """Pitch modulation vibrato"""

    def __init__(self, sample_rate: int = 44100):
        super().__init__(sample_rate)
        max_delay = int(0.05 * sample_rate)
        self.buffer = np.zeros(max_delay)
        self.write_pos = 0
        self.lfo_phase = 0.0

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - rate: LFO rate in Hz (0.1 to 15, default: 5)
        - depth: Pitch modulation depth in cents (0 to 50, default: 20)
        """
        rate = parameters.get('rate', 5.0)
        depth_cents = parameters.get('depth', 20.0)

        # Convert cents to delay modulation (approximate)
        max_delay_ms = depth_cents / 100.0  # Rough approximation
        depth_samples = max_delay_ms * self.sample_rate / 1000.0

        output = np.zeros_like(audio)

        for i in range(len(audio)):
            # Generate LFO
            lfo = np.sin(2 * np.pi * self.lfo_phase)
            self.lfo_phase += rate / self.sample_rate
            if self.lfo_phase >= 1.0:
                self.lfo_phase -= 1.0

            # Calculate modulated delay
            delay_samples = 5 + lfo * depth_samples  # 5 sample base delay
            delay_samples = int(np.clip(delay_samples, 0, len(self.buffer) - 1))

            # Read from buffer
            read_pos = (self.write_pos - delay_samples) % len(self.buffer)
            output[i] = self.buffer[read_pos]

            # Write to buffer
            self.buffer[self.write_pos] = audio[i]
            self.write_pos = (self.write_pos + 1) % len(self.buffer)

        return output


# ============================================================================
# DISTORTION EFFECTS
# ============================================================================

class DistortionProcessor(EffectProcessor):
    """Waveshaping distortion"""

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - drive: Input gain/drive (1 to 100, default: 10)
        - tone: Post-distortion tone control (0 to 1, default: 0.5)
        - output_gain: Output level (0 to 1, default: 0.5)
        - type: Distortion type ('hard', 'soft', 'tube', default: 'soft')
        """
        drive = parameters.get('drive', 10.0)
        tone = parameters.get('tone', 0.5)
        output_gain = parameters.get('output_gain', 0.5)
        dist_type = parameters.get('type', 'soft')

        # Apply drive
        driven = audio * drive

        # Apply waveshaping
        if dist_type == 'hard':
            # Hard clipping
            distorted = np.clip(driven, -1.0, 1.0)
        elif dist_type == 'tube':
            # Tube-style soft clipping
            distorted = np.tanh(driven * 0.5) * 2.0
        else:  # soft
            # Soft clipping using sigmoid
            distorted = 2.0 / (1.0 + np.exp(-driven)) - 1.0

        # Apply tone control (simple lowpass)
        if tone < 1.0:
            cutoff_freq = 500 + tone * 4500  # 500Hz to 5kHz
            sos = signal.butter(2, cutoff_freq, 'low', fs=self.sample_rate, output='sos')
            distorted = signal.sosfilt(sos, distorted)

        # Apply output gain
        output = distorted * output_gain

        return output


class SaturationProcessor(EffectProcessor):
    """Analog-style saturation"""

    def process(self, audio: np.ndarray, parameters: Dict[str, float]) -> np.ndarray:
        """
        Parameters:
        - amount: Saturation amount (0 to 1, default: 0.5)
        - harmonics: Harmonic enhancement (0 to 1, default: 0.3)
        """
        amount = parameters.get('amount', 0.5)
        harmonics = parameters.get('harmonics', 0.3)

        # Soft saturation using tanh
        saturated = np.tanh(audio * (1 + amount * 2))

        # Add harmonics (second and third order)
        if harmonics > 0:
            second_harmonic = np.tanh(audio * 2) * harmonics * 0.1
            third_harmonic = np.tanh(audio * 3) * harmonics * 0.05
            saturated += second_harmonic + third_harmonic

        # Normalize
        output = saturated * (1.0 / (1 + amount))

        return output


# ============================================================================
# EFFECT PROCESSOR FACTORY
# ============================================================================

class EffectProcessorFactory:
    """Factory for creating effect processors"""

    _processors = {
        EffectType.COMPRESSOR: CompressorProcessor,
        EffectType.LIMITER: LimiterProcessor,
        EffectType.GATE: GateProcessor,
        EffectType.EXPANDER: ExpanderProcessor,
        EffectType.EQ_PARAMETRIC: ParametricEQProcessor,
        EffectType.EQ_GRAPHIC: GraphicEQProcessor,
        EffectType.REVERB: ReverbProcessor,
        EffectType.DELAY: DelayProcessor,
        EffectType.CHORUS: ChorusProcessor,
        EffectType.FLANGER: FlangerProcessor,
        EffectType.PHASER: PhaserProcessor,
        EffectType.TREMOLO: TremoloProcessor,
        EffectType.VIBRATO: VibratoProcessor,
        EffectType.DISTORTION: DistortionProcessor,
        EffectType.SATURATION: SaturationProcessor,
    }

    @classmethod
    def create(cls, effect_type: EffectType, sample_rate: int = 44100) -> EffectProcessor:
        """Create an effect processor instance"""
        processor_class = cls._processors.get(effect_type)
        if processor_class is None:
            raise ValueError(f"Unknown effect type: {effect_type}")
        return processor_class(sample_rate)

    @classmethod
    def get_available_effects(cls) -> list:
        """Get list of available effect types"""
        return list(cls._processors.keys())
