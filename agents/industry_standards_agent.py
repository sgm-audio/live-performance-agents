"""
Industry Standards Agent

Performs detailed analysis and comparison of audio against industry standards including
EBU R128, ATSC A/85, ITU-R BS.1770, streaming platform specs, broadcast standards,
and live sound best practices.
"""

import numpy as np
import threading
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


class StandardType(Enum):
    """Audio standard types"""
    EBU_R128 = "ebu_r128"
    ATSC_A85 = "atsc_a85"
    ITU_BS1770 = "itu_bs1770"
    SPOTIFY = "spotify"
    APPLE_MUSIC = "apple_music"
    YOUTUBE = "youtube"
    BROADCAST = "broadcast"
    LIVE_SOUND = "live_sound"
    CINEMA = "cinema"
    STREAMING = "streaming"


@dataclass
class LoudnessStandard:
    """Loudness standard specification"""
    standard_name: str
    target_lufs: float
    max_true_peak_db: float
    measurement_method: str
    tolerance_lu: float = 1.0
    gating_threshold_db: float = -10.0
    description: str = ""


@dataclass
class StreamingPlatformSpec:
    """Streaming platform specification"""
    platform_name: str
    target_lufs: float
    max_true_peak_db: float
    normalization: bool
    sample_rate: int
    bit_depth: int
    codec: str
    additional_requirements: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceReport:
    """Standards compliance report"""
    standard_type: StandardType
    compliant: bool
    measured_lufs: float
    target_lufs: float
    lufs_difference: float
    measured_true_peak: float
    max_true_peak: float
    dynamic_range: float
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class DetailedAnalysisReport:
    """Comprehensive audio analysis report"""
    overall_compliance: bool
    compliant_standards: List[str] = field(default_factory=list)
    non_compliant_standards: List[str] = field(default_factory=list)
    measurements: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    impact_assessment: str = ""
    quality_score: float = 0.0


class IndustryStandardsAgent(BaseAgent):
    """
    Agent for industry standards analysis and compliance checking.

    Standards Covered:
    - EBU R128 (European Broadcasting Union)
    - ATSC A/85 (Advanced Television Systems Committee)
    - ITU-R BS.1770 (International Telecommunication Union)
    - Streaming platforms (Spotify, Apple Music, YouTube, etc.)
    - Broadcast standards
    - Live sound best practices
    """

    def __init__(self):
        super().__init__(
            agent_id="industry_standards_agent",
            agent_name="Industry Standards Agent"
        )

        # Define industry standards
        self.loudness_standards = self._initialize_loudness_standards()
        self.streaming_specs = self._initialize_streaming_specs()

        # Analysis cache
        self.analysis_cache: Dict[str, ComplianceReport] = {}
        self.cache_lock = threading.Lock()

        # Statistics
        self.stats = {
            'analyses_performed': 0,
            'compliance_checks': 0,
            'recommendations_generated': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the standards agent"""
        self.subscribe("standards.analyze")
        self.subscribe("standards.compare")
        self.subscribe("standards.recommend")
        self.subscribe("standards.report.generate")
        self.subscribe("audio.quality.check")

        self.log("INFO", "Industry Standards Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self.log("INFO", "Industry Standards Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "standards.analyze":
                self._handle_analyze(message)
            elif message.topic == "standards.compare":
                self._handle_compare(message)
            elif message.topic == "standards.recommend":
                self._handle_recommend(message)
            elif message.topic == "standards.report.generate":
                self._handle_report_generate(message)
            elif message.topic == "audio.quality.check":
                self._handle_quality_check(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_analyze(self, message: Message):
        """Handle standards analysis request"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))
        sample_rate = payload.get('sample_rate', 48000)
        standard_types = payload.get('standards', [StandardType.EBU_R128.value])

        if len(audio_data) == 0:
            self.respond(message, {'success': False, 'error': 'No audio data'})
            return

        # Analyze against each standard
        compliance_reports = []

        for standard_name in standard_types:
            try:
                standard_type = StandardType(standard_name)
                report = self._analyze_against_standard(audio_data, sample_rate, standard_type)
                compliance_reports.append(report)

                with self.cache_lock:
                    self.analysis_cache[f"{standard_name}_{time.time()}"] = report

            except Exception as e:
                logger.error(f"Error analyzing {standard_name}: {e}")

        with self.stats_lock:
            self.stats['analyses_performed'] += 1
            self.stats['compliance_checks'] += len(compliance_reports)

        self.respond(message, {
            'success': True,
            'reports': [self._report_to_dict(r) for r in compliance_reports]
        })

    def _handle_compare(self, message: Message):
        """Handle comparison across multiple standards"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))
        sample_rate = payload.get('sample_rate', 48000)

        # Analyze against all major standards
        all_standards = [
            StandardType.EBU_R128,
            StandardType.SPOTIFY,
            StandardType.APPLE_MUSIC,
            StandardType.YOUTUBE,
            StandardType.BROADCAST
        ]

        comparison = {}

        for standard_type in all_standards:
            report = self._analyze_against_standard(audio_data, sample_rate, standard_type)
            comparison[standard_type.value] = self._report_to_dict(report)

        self.respond(message, {
            'success': True,
            'comparison': comparison,
            'best_match': self._find_best_matching_standard(comparison)
        })

    def _handle_recommend(self, message: Message):
        """Handle recommendations request"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))
        sample_rate = payload.get('sample_rate', 48000)
        target_platform = payload.get('target_platform', 'broadcast')

        # Analyze current state
        measurements = self._measure_audio_parameters(audio_data, sample_rate)

        # Generate recommendations
        recommendations = self._generate_recommendations(measurements, target_platform)

        self.respond(message, {
            'success': True,
            'measurements': measurements,
            'recommendations': recommendations
        })

        with self.stats_lock:
            self.stats['recommendations_generated'] += len(recommendations)

    def _handle_report_generate(self, message: Message):
        """Handle detailed report generation"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))
        sample_rate = payload.get('sample_rate', 48000)
        target_standards = payload.get('target_standards', ['ebu_r128', 'spotify'])

        # Generate comprehensive report
        report = self._generate_detailed_report(audio_data, sample_rate, target_standards)

        self.respond(message, {
            'success': True,
            'report': self._detailed_report_to_dict(report)
        })

    def _handle_quality_check(self, message: Message):
        """Handle quick quality check"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))
        sample_rate = payload.get('sample_rate', 48000)

        # Quick analysis
        measurements = self._measure_audio_parameters(audio_data, sample_rate)

        # Check against EBU R128 (most common)
        report = self._analyze_against_standard(audio_data, sample_rate, StandardType.EBU_R128)

        self.respond(message, {
            'success': True,
            'compliant': report.compliant,
            'quality_score': self._calculate_quality_score(measurements),
            'quick_recommendations': report.recommendations[:3]
        })

    def _initialize_loudness_standards(self) -> Dict[StandardType, LoudnessStandard]:
        """Initialize loudness standards database"""
        return {
            StandardType.EBU_R128: LoudnessStandard(
                standard_name="EBU R128",
                target_lufs=-23.0,
                max_true_peak_db=-1.0,
                measurement_method="ITU-R BS.1770-4",
                tolerance_lu=1.0,
                description="European Broadcasting Union loudness normalization"
            ),
            StandardType.ATSC_A85: LoudnessStandard(
                standard_name="ATSC A/85",
                target_lufs=-24.0,
                max_true_peak_db=-2.0,
                measurement_method="ITU-R BS.1770-4",
                tolerance_lu=2.0,
                description="US broadcast loudness standard"
            ),
            StandardType.ITU_BS1770: LoudnessStandard(
                standard_name="ITU-R BS.1770",
                target_lufs=-23.0,
                max_true_peak_db=-1.0,
                measurement_method="ITU-R BS.1770-4",
                tolerance_lu=1.0,
                description="International loudness measurement standard"
            ),
            StandardType.BROADCAST: LoudnessStandard(
                standard_name="Broadcast Generic",
                target_lufs=-23.0,
                max_true_peak_db=-1.0,
                measurement_method="ITU-R BS.1770-4",
                tolerance_lu=1.0,
                description="General broadcast loudness standard"
            ),
            StandardType.LIVE_SOUND: LoudnessStandard(
                standard_name="Live Sound",
                target_lufs=-18.0,  # Hotter for live
                max_true_peak_db=-3.0,
                measurement_method="Short-term LUFS",
                tolerance_lu=3.0,
                description="Live sound reinforcement best practices"
            ),
            StandardType.CINEMA: LoudnessStandard(
                standard_name="Cinema",
                target_lufs=-27.0,  # SMPTE ST-2067-3
                max_true_peak_db=-6.0,
                measurement_method="ITU-R BS.1770-4",
                tolerance_lu=2.0,
                description="Cinema audio standard (SMPTE)"
            )
        }

    def _initialize_streaming_specs(self) -> Dict[str, StreamingPlatformSpec]:
        """Initialize streaming platform specifications"""
        return {
            'spotify': StreamingPlatformSpec(
                platform_name="Spotify",
                target_lufs=-14.0,
                max_true_peak_db=-1.0,
                normalization=True,
                sample_rate=44100,
                bit_depth=16,
                codec="Ogg Vorbis / AAC",
                additional_requirements={
                    'dynamic_range_min': 8.0,
                    'recommended_lufs_range': (-16.0, -14.0)
                }
            ),
            'apple_music': StreamingPlatformSpec(
                platform_name="Apple Music",
                target_lufs=-16.0,
                max_true_peak_db=-1.0,
                normalization=True,
                sample_rate=44100,
                bit_depth=16,
                codec="AAC",
                additional_requirements={
                    'sound_check': True,
                    'mastered_for_itunes': {
                        'sample_rate': 96000,
                        'bit_depth': 24
                    }
                }
            ),
            'youtube': StreamingPlatformSpec(
                platform_name="YouTube",
                target_lufs=-13.0,  # to -15.0 range
                max_true_peak_db=-1.0,
                normalization=True,
                sample_rate=48000,
                bit_depth=16,
                codec="AAC",
                additional_requirements={
                    'recommended_lufs': -13.0,
                    'max_lufs': -13.0
                }
            ),
            'tidal': StreamingPlatformSpec(
                platform_name="TIDAL",
                target_lufs=-14.0,
                max_true_peak_db=-1.0,
                normalization=True,
                sample_rate=48000,
                bit_depth=24,
                codec="FLAC / MQA",
                additional_requirements={
                    'hifi_recommended': {
                        'sample_rate': 96000,
                        'bit_depth': 24
                    }
                }
            ),
            'amazon_music': StreamingPlatformSpec(
                platform_name="Amazon Music",
                target_lufs=-14.0,
                max_true_peak_db=-2.0,
                normalization=True,
                sample_rate=44100,
                bit_depth=16,
                codec="AAC",
                additional_requirements={}
            ),
            'soundcloud': StreamingPlatformSpec(
                platform_name="SoundCloud",
                target_lufs=-14.0,
                max_true_peak_db=-1.0,
                normalization=False,
                sample_rate=48000,
                bit_depth=16,
                codec="MP3 / Opus",
                additional_requirements={
                    'max_file_size_mb': 500
                }
            )
        }

    def _analyze_against_standard(self, audio: np.ndarray, sample_rate: int,
                                   standard_type: StandardType) -> ComplianceReport:
        """Analyze audio against a specific standard"""
        # Measure audio parameters
        measurements = self._measure_audio_parameters(audio, sample_rate)

        # Get standard specification
        if standard_type in self.loudness_standards:
            standard = self.loudness_standards[standard_type]
            target_lufs = standard.target_lufs
            max_peak = standard.max_true_peak_db
            tolerance = standard.tolerance_lu
        elif standard_type.value in ['spotify', 'apple_music', 'youtube']:
            platform_key = standard_type.value.lower()
            if platform_key in self.streaming_specs:
                spec = self.streaming_specs[platform_key]
                target_lufs = spec.target_lufs
                max_peak = spec.max_true_peak_db
                tolerance = 1.0
            else:
                target_lufs = -14.0
                max_peak = -1.0
                tolerance = 1.0
        else:
            target_lufs = -23.0
            max_peak = -1.0
            tolerance = 1.0

        measured_lufs = measurements['lufs_integrated']
        measured_peak = measurements['true_peak_db']
        lufs_diff = measured_lufs - target_lufs

        # Check compliance
        lufs_compliant = abs(lufs_diff) <= tolerance
        peak_compliant = measured_peak <= max_peak
        compliant = lufs_compliant and peak_compliant

        # Generate recommendations
        recommendations = []
        warnings = []

        if not lufs_compliant:
            if lufs_diff > 0:
                recommendations.append(
                    f"Reduce overall gain by {abs(lufs_diff):.1f} dB to meet {target_lufs} LUFS target"
                )
                warnings.append(f"Audio is {abs(lufs_diff):.1f} LU too loud")
            else:
                recommendations.append(
                    f"Increase overall gain by {abs(lufs_diff):.1f} dB to meet {target_lufs} LUFS target"
                )
                warnings.append(f"Audio is {abs(lufs_diff):.1f} LU too quiet")

        if not peak_compliant:
            peak_over = measured_peak - max_peak
            recommendations.append(
                f"Apply {peak_over:.1f} dB of peak limiting to stay below {max_peak} dBTP"
            )
            warnings.append(f"True peak exceeds maximum by {peak_over:.1f} dB")

        # Dynamic range check
        if measurements['dynamic_range_db'] < 6.0:
            recommendations.append(
                "Consider reducing compression/limiting to increase dynamic range (currently very compressed)"
            )
            warnings.append("Very low dynamic range detected - possible over-compression")
        elif measurements['dynamic_range_db'] > 20.0:
            recommendations.append(
                "Consider compression to reduce excessive dynamic range for consistent playback"
            )

        # Platform-specific recommendations
        if standard_type == StandardType.SPOTIFY:
            recommendations.append(
                "Maintain at least 8 dB of dynamic range for best Spotify playback quality"
            )
        elif standard_type == StandardType.APPLE_MUSIC:
            recommendations.append(
                "Consider 'Mastered for iTunes' format: 24-bit/96kHz for premium quality"
            )
        elif standard_type == StandardType.YOUTUBE:
            recommendations.append(
                "YouTube normalizes to -13 LUFS; audio louder than this will be turned down"
            )
        elif standard_type == StandardType.LIVE_SOUND:
            recommendations.append(
                "Maintain headroom for dynamic peaks in live performance (-3 to -6 dBFS)"
            )
            recommendations.append(
                "Monitor short-term LUFS for consistent audience experience"
            )

        return ComplianceReport(
            standard_type=standard_type,
            compliant=compliant,
            measured_lufs=measured_lufs,
            target_lufs=target_lufs,
            lufs_difference=lufs_diff,
            measured_true_peak=measured_peak,
            max_true_peak=max_peak,
            dynamic_range=measurements['dynamic_range_db'],
            recommendations=recommendations,
            warnings=warnings,
            timestamp=time.time()
        )

    def _measure_audio_parameters(self, audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
        """Measure comprehensive audio parameters"""
        # Basic measurements
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))

        # LUFS calculation (simplified - real implementation uses ITU-R BS.1770-4)
        lufs_integrated = -23.0 + 20 * np.log10(rms + 1e-10)
        lufs_short_term = lufs_integrated  # Simplified
        lufs_momentary = lufs_integrated  # Simplified

        # True peak (simplified - real implementation uses 4x oversampling)
        true_peak_db = 20 * np.log10(peak + 1e-10)

        # Dynamic range
        noise_floor = np.percentile(np.abs(audio), 10)
        dynamic_range_db = 20 * np.log10((peak + 1e-10) / (noise_floor + 1e-10))

        # Crest factor
        crest_factor = peak / (rms + 1e-10)
        crest_factor_db = 20 * np.log10(crest_factor)

        # RMS level
        rms_db = 20 * np.log10(rms + 1e-10)

        # SNR estimate
        signal_level = np.percentile(np.abs(audio), 90)
        noise_level = np.percentile(np.abs(audio), 10)
        snr_db = 20 * np.log10((signal_level + 1e-10) / (noise_level + 1e-10))

        # Phase correlation (for stereo)
        phase_correlation = 1.0  # Placeholder

        return {
            'lufs_integrated': lufs_integrated,
            'lufs_short_term': lufs_short_term,
            'lufs_momentary': lufs_momentary,
            'true_peak_db': true_peak_db,
            'rms_db': rms_db,
            'dynamic_range_db': dynamic_range_db,
            'crest_factor_db': crest_factor_db,
            'snr_db': snr_db,
            'phase_correlation': phase_correlation,
            'peak_amplitude': peak
        }

    def _generate_recommendations(self, measurements: Dict[str, float],
                                  target_platform: str) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Get platform spec
        if target_platform in self.streaming_specs:
            spec = self.streaming_specs[target_platform]

            lufs_diff = measurements['lufs_integrated'] - spec.target_lufs

            if abs(lufs_diff) > 1.0:
                if lufs_diff > 0:
                    recommendations.append(
                        f"Reduce gain by {abs(lufs_diff):.1f} dB for {spec.platform_name} ({spec.target_lufs} LUFS)"
                    )
                else:
                    recommendations.append(
                        f"Increase gain by {abs(lufs_diff):.1f} dB for {spec.platform_name} ({spec.target_lufs} LUFS)"
                    )

            if measurements['true_peak_db'] > spec.max_true_peak_db:
                recommendations.append(
                    f"Apply true peak limiting to {spec.max_true_peak_db} dBTP for {spec.platform_name}"
                )

        # Dynamic range recommendations
        if measurements['dynamic_range_db'] < 6.0:
            recommendations.append(
                "Reduce compression/limiting - current dynamic range is very low (< 6 dB)"
            )
            recommendations.append(
                "Over-compression can cause listener fatigue and poor streaming platform performance"
            )
        elif measurements['dynamic_range_db'] < 8.0:
            recommendations.append(
                "Consider slight reduction in compression for better dynamics (< 8 dB range)"
            )

        # Crest factor recommendations
        if measurements['crest_factor_db'] < 6.0:
            recommendations.append(
                "Low crest factor indicates heavy limiting - consider more transparent dynamics processing"
            )

        # SNR recommendations
        if measurements['snr_db'] < 40.0:
            recommendations.append(
                f"Signal-to-noise ratio is low ({measurements['snr_db']:.1f} dB) - check for noise floor issues"
            )

        return recommendations

    def _generate_detailed_report(self, audio: np.ndarray, sample_rate: int,
                                  target_standards: List[str]) -> DetailedAnalysisReport:
        """Generate comprehensive analysis report"""
        measurements = self._measure_audio_parameters(audio, sample_rate)

        compliant_standards = []
        non_compliant_standards = []
        all_recommendations = []
        all_warnings = []

        # Analyze against each target standard
        for standard_name in target_standards:
            try:
                standard_type = StandardType(standard_name)
                report = self._analyze_against_standard(audio, sample_rate, standard_type)

                if report.compliant:
                    compliant_standards.append(standard_name)
                else:
                    non_compliant_standards.append(standard_name)

                all_recommendations.extend(report.recommendations)
                all_warnings.extend(report.warnings)

            except Exception as e:
                logger.error(f"Error analyzing {standard_name}: {e}")

        # Generate impact assessment
        impact_assessment = self._generate_impact_assessment(
            measurements, compliant_standards, non_compliant_standards
        )

        # Calculate quality score
        quality_score = self._calculate_quality_score(measurements)

        return DetailedAnalysisReport(
            overall_compliance=len(non_compliant_standards) == 0,
            compliant_standards=compliant_standards,
            non_compliant_standards=non_compliant_standards,
            measurements=measurements,
            recommendations=list(set(all_recommendations)),  # Remove duplicates
            impact_assessment=impact_assessment,
            quality_score=quality_score
        )

    def _generate_impact_assessment(self, measurements: Dict[str, float],
                                    compliant: List[str],
                                    non_compliant: List[str]) -> str:
        """Generate impact assessment of non-compliance"""
        if not non_compliant:
            return "Audio meets all target standards. No negative impact expected."

        impacts = []

        if 'spotify' in non_compliant or 'apple_music' in non_compliant:
            impacts.append(
                "Streaming platforms will apply normalization, potentially reducing perceived loudness and impact. "
                "Over-compressed audio may sound dull after normalization."
            )

        if 'ebu_r128' in non_compliant or 'broadcast' in non_compliant:
            impacts.append(
                "Broadcast delivery may be rejected or require remastering. "
                "Inconsistent loudness can result in viewer complaints and regulatory issues."
            )

        if measurements['dynamic_range_db'] < 6.0:
            impacts.append(
                "Severely limited dynamic range can cause listener fatigue, "
                "reduced emotional impact, and poor performance on modern streaming platforms. "
                "Potential for distortion artifacts on some playback systems."
            )

        if measurements['true_peak_db'] > -1.0:
            impacts.append(
                "True peaks exceeding -1.0 dBTP may cause clipping and distortion "
                "during format conversion (e.g., MP3 encoding) or on certain playback devices. "
                "Risk of intersample peaks causing audible artifacts."
            )

        if measurements['lufs_integrated'] > -10.0:
            impacts.append(
                "Extremely loud mastering will be significantly reduced by streaming platforms, "
                "potentially making the audio sound worse than properly normalized masters. "
                "'Loudness war' mastering is counterproductive in the streaming era."
            )

        if not impacts:
            impacts.append("Non-compliance may result in suboptimal playback experience.")

        return " ".join(impacts)

    def _calculate_quality_score(self, measurements: Dict[str, float]) -> float:
        """Calculate overall quality score (0-100)"""
        score = 100.0

        # Penalize for poor dynamic range
        if measurements['dynamic_range_db'] < 6.0:
            score -= 30.0
        elif measurements['dynamic_range_db'] < 8.0:
            score -= 15.0
        elif measurements['dynamic_range_db'] < 10.0:
            score -= 5.0

        # Penalize for peak issues
        if measurements['true_peak_db'] > -1.0:
            score -= 20.0
        elif measurements['true_peak_db'] > -2.0:
            score -= 10.0

        # Penalize for extreme loudness
        if measurements['lufs_integrated'] > -10.0:
            score -= 25.0
        elif measurements['lufs_integrated'] > -12.0:
            score -= 15.0

        # Penalize for very quiet audio
        if measurements['lufs_integrated'] < -30.0:
            score -= 20.0

        # Penalize for poor SNR
        if measurements['snr_db'] < 40.0:
            score -= 15.0

        return max(0.0, min(100.0, score))

    def _find_best_matching_standard(self, comparison: Dict[str, Any]) -> str:
        """Find which standard the audio best matches"""
        best_standard = None
        min_lufs_diff = float('inf')

        for standard_name, report_dict in comparison.items():
            lufs_diff = abs(report_dict.get('lufs_difference', 999))
            if lufs_diff < min_lufs_diff:
                min_lufs_diff = lufs_diff
                best_standard = standard_name

        return best_standard or "unknown"

    def _report_to_dict(self, report: ComplianceReport) -> Dict[str, Any]:
        """Convert compliance report to dictionary"""
        return {
            'standard': report.standard_type.value,
            'compliant': report.compliant,
            'measured_lufs': report.measured_lufs,
            'target_lufs': report.target_lufs,
            'lufs_difference': report.lufs_difference,
            'measured_true_peak': report.measured_true_peak,
            'max_true_peak': report.max_true_peak,
            'dynamic_range': report.dynamic_range,
            'recommendations': report.recommendations,
            'warnings': report.warnings
        }

    def _detailed_report_to_dict(self, report: DetailedAnalysisReport) -> Dict[str, Any]:
        """Convert detailed report to dictionary"""
        return {
            'overall_compliance': report.overall_compliance,
            'compliant_standards': report.compliant_standards,
            'non_compliant_standards': report.non_compliant_standards,
            'measurements': report.measurements,
            'recommendations': report.recommendations,
            'impact_assessment': report.impact_assessment,
            'quality_score': report.quality_score
        }
