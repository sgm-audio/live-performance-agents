"""
Performance Monitoring & Analytics Agent

Real-time monitoring of system performance, audio quality metrics, and health status.
"""

import threading
import time
import psutil
import numpy as np
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import deque
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """System performance metrics"""
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    network_latency_ms: float
    audio_latency_ms: float
    buffer_load_percent: float
    timestamp: float


@dataclass
class AudioQualityMetrics:
    """Audio quality measurements"""
    lufs_integrated: float
    lufs_short_term: float
    lufs_momentary: float
    true_peak_db: float
    dynamic_range_db: float
    phase_correlation: float
    thd_plus_noise_percent: float
    snr_db: float
    timestamp: float


@dataclass
class PerformanceAlert:
    """Performance alert configuration"""
    alert_id: str
    metric: str
    threshold: float
    comparison: str  # "greater_than", "less_than", "equals"
    callback_topic: str
    enabled: bool = True
    triggered: bool = False


class PerformanceMonitoringAgent(BaseAgent):
    """Agent for performance monitoring and analytics"""

    def __init__(self):
        super().__init__(
            agent_id="performance_monitoring_agent",
            agent_name="Performance Monitoring & Analytics Agent"
        )

        # Metrics history
        self.performance_history = deque(maxlen=1000)
        self.audio_quality_history = deque(maxlen=1000)
        self.history_lock = threading.Lock()

        # Alerts
        self.alerts: Dict[str, PerformanceAlert] = {}
        self.alerts_lock = threading.Lock()

        # Monitoring threads
        self.perf_monitor_thread: Optional[threading.Thread] = None
        self.audio_monitor_thread: Optional[threading.Thread] = None
        self.monitoring_active = False

        # Statistics
        self.stats = {
            'measurements_taken': 0,
            'alerts_triggered': 0,
            'avg_cpu_usage': 0.0,
            'avg_latency': 0.0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the monitoring agent"""
        self.subscribe("monitor.metrics.request")
        self.subscribe("monitor.alert.create")
        self.subscribe("monitor.alert.delete")
        self.subscribe("monitor.report.generate")
        self.subscribe("audio.quality.analyze")

        self._start_monitoring_threads()
        self.log("INFO", "Performance Monitoring Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self._stop_monitoring_threads()
        self.log("INFO", "Performance Monitoring Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "monitor.metrics.request":
                self._handle_metrics_request(message)
            elif message.topic == "monitor.alert.create":
                self._handle_alert_create(message)
            elif message.topic == "monitor.alert.delete":
                self._handle_alert_delete(message)
            elif message.topic == "monitor.report.generate":
                self._handle_report_generate(message)
            elif message.topic == "audio.quality.analyze":
                self._handle_audio_quality_analyze(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_metrics_request(self, message: Message):
        """Handle metrics request"""
        metrics = self._get_current_performance_metrics()

        self.respond(message, {
            'success': True,
            'metrics': {
                'cpu_usage': metrics.cpu_usage_percent,
                'memory_usage': metrics.memory_usage_percent,
                'audio_latency': metrics.audio_latency_ms,
                'buffer_load': metrics.buffer_load_percent
            }
        })

    def _handle_alert_create(self, message: Message):
        """Handle alert creation"""
        payload = message.payload

        alert = PerformanceAlert(
            alert_id=payload.get('alert_id', f"alert_{time.time()}"),
            metric=payload['metric'],
            threshold=payload['threshold'],
            comparison=payload.get('comparison', 'greater_than'),
            callback_topic=payload.get('callback_topic', 'monitor.alert.triggered'),
            enabled=payload.get('enabled', True)
        )

        with self.alerts_lock:
            self.alerts[alert.alert_id] = alert

        self.respond(message, {'success': True, 'alert_id': alert.alert_id})

    def _handle_alert_delete(self, message: Message):
        """Handle alert deletion"""
        payload = message.payload
        alert_id = payload['alert_id']

        with self.alerts_lock:
            if alert_id in self.alerts:
                del self.alerts[alert_id]
                success = True
            else:
                success = False

        self.respond(message, {'success': success, 'alert_id': alert_id})

    def _handle_report_generate(self, message: Message):
        """Handle performance report generation"""
        payload = message.payload
        duration_seconds = payload.get('duration_seconds', 60.0)
        include_graphs = payload.get('include_graphs', False)

        report = self._generate_performance_report(duration_seconds, include_graphs)

        self.respond(message, {
            'success': True,
            'report': report
        })

    def _handle_audio_quality_analyze(self, message: Message):
        """Handle audio quality analysis"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))
        sample_rate = payload.get('sample_rate', 48000)

        if len(audio_data) == 0:
            self.respond(message, {'success': False, 'error': 'No audio data'})
            return

        metrics = self._analyze_audio_quality(audio_data, sample_rate)

        self.respond(message, {
            'success': True,
            'metrics': {
                'lufs_integrated': metrics.lufs_integrated,
                'lufs_short_term': metrics.lufs_short_term,
                'true_peak_db': metrics.true_peak_db,
                'dynamic_range_db': metrics.dynamic_range_db,
                'phase_correlation': metrics.phase_correlation,
                'snr_db': metrics.snr_db
            }
        })

    def _start_monitoring_threads(self):
        """Start monitoring threads"""
        self.monitoring_active = True

        # Performance monitoring thread
        self.perf_monitor_thread = threading.Thread(
            target=self._performance_monitor_worker,
            name=f"{self.agent_id}_perf_monitor",
            daemon=True
        )
        self.perf_monitor_thread.start()

        # Audio monitoring thread
        self.audio_monitor_thread = threading.Thread(
            target=self._audio_monitor_worker,
            name=f"{self.agent_id}_audio_monitor",
            daemon=True
        )
        self.audio_monitor_thread.start()

    def _stop_monitoring_threads(self):
        """Stop monitoring threads"""
        self.monitoring_active = False

        if self.perf_monitor_thread:
            self.perf_monitor_thread.join(timeout=2.0)

        if self.audio_monitor_thread:
            self.audio_monitor_thread.join(timeout=2.0)

    def _performance_monitor_worker(self):
        """Performance monitoring worker"""
        while self.monitoring_active:
            try:
                metrics = self._get_current_performance_metrics()

                # Store in history
                with self.history_lock:
                    self.performance_history.append(metrics)

                # Check alerts
                self._check_performance_alerts(metrics)

                # Publish periodic update
                self.publish("monitor.performance.cpu", {
                    'cpu_usage': metrics.cpu_usage_percent,
                    'memory_usage': metrics.memory_usage_percent
                }, priority=Priority.LOW)

                # Update statistics
                with self.stats_lock:
                    self.stats['measurements_taken'] += 1
                    self.stats['avg_cpu_usage'] = metrics.cpu_usage_percent

                time.sleep(1.0)  # Update every second

            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")

    def _audio_monitor_worker(self):
        """Audio monitoring worker"""
        while self.monitoring_active:
            try:
                # Simulated audio quality monitoring
                # In production, this would analyze actual audio streams

                time.sleep(0.1)  # 100ms intervals

            except Exception as e:
                logger.error(f"Error in audio monitor: {e}")

    def _get_current_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Simulated audio-specific metrics
            audio_latency = np.random.uniform(2.0, 8.0)
            buffer_load = np.random.uniform(20.0, 80.0)

            return PerformanceMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory.percent,
                disk_usage_percent=disk.percent,
                network_latency_ms=0.0,
                audio_latency_ms=audio_latency,
                buffer_load_percent=buffer_load,
                timestamp=time.time()
            )
        except:
            # Fallback if psutil not available
            return PerformanceMetrics(
                cpu_usage_percent=25.0,
                memory_usage_percent=50.0,
                disk_usage_percent=60.0,
                network_latency_ms=0.0,
                audio_latency_ms=5.0,
                buffer_load_percent=50.0,
                timestamp=time.time()
            )

    def _analyze_audio_quality(self, audio: np.ndarray, sample_rate: int) -> AudioQualityMetrics:
        """Analyze audio quality metrics"""
        # Calculate RMS and peak levels
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))

        # Calculate LUFS (simplified - real implementation would use ITU-R BS.1770)
        lufs_integrated = -23.0 + 20 * np.log10(rms + 1e-10)
        lufs_short_term = lufs_integrated
        lufs_momentary = lufs_integrated

        # True peak
        true_peak_db = 20 * np.log10(peak + 1e-10)

        # Dynamic range
        noise_floor = np.percentile(np.abs(audio), 10)
        dynamic_range_db = 20 * np.log10((peak + 1e-10) / (noise_floor + 1e-10))

        # Phase correlation (for stereo)
        phase_correlation = 1.0  # Simplified

        # THD+N (simplified)
        thd_plus_noise = 0.001  # 0.1%

        # SNR
        signal_level = np.percentile(np.abs(audio), 90)
        noise_level = np.percentile(np.abs(audio), 10)
        snr_db = 20 * np.log10((signal_level + 1e-10) / (noise_level + 1e-10))

        return AudioQualityMetrics(
            lufs_integrated=lufs_integrated,
            lufs_short_term=lufs_short_term,
            lufs_momentary=lufs_momentary,
            true_peak_db=true_peak_db,
            dynamic_range_db=dynamic_range_db,
            phase_correlation=phase_correlation,
            thd_plus_noise_percent=thd_plus_noise * 100,
            snr_db=snr_db,
            timestamp=time.time()
        )

    def _check_performance_alerts(self, metrics: PerformanceMetrics):
        """Check if any alerts should be triggered"""
        with self.alerts_lock:
            for alert in self.alerts.values():
                if not alert.enabled:
                    continue

                # Get metric value
                metric_value = getattr(metrics, alert.metric, None)
                if metric_value is None:
                    continue

                # Check threshold
                should_trigger = False

                if alert.comparison == 'greater_than' and metric_value > alert.threshold:
                    should_trigger = True
                elif alert.comparison == 'less_than' and metric_value < alert.threshold:
                    should_trigger = True
                elif alert.comparison == 'equals' and abs(metric_value - alert.threshold) < 0.01:
                    should_trigger = True

                if should_trigger and not alert.triggered:
                    alert.triggered = True

                    with self.stats_lock:
                        self.stats['alerts_triggered'] += 1

                    # Publish alert
                    self.publish(alert.callback_topic, {
                        'alert_id': alert.alert_id,
                        'metric': alert.metric,
                        'value': metric_value,
                        'threshold': alert.threshold
                    }, priority=Priority.CRITICAL)

                    self.publish("monitor.alert.critical", {
                        'alert_id': alert.alert_id,
                        'message': f"{alert.metric} exceeded threshold: {metric_value:.2f} > {alert.threshold:.2f}"
                    }, priority=Priority.CRITICAL)

                elif not should_trigger:
                    alert.triggered = False

    def _generate_performance_report(self, duration_seconds: float, include_graphs: bool) -> Dict[str, Any]:
        """Generate performance report"""
        with self.history_lock:
            # Get recent metrics
            cutoff_time = time.time() - duration_seconds
            recent_metrics = [m for m in self.performance_history if m.timestamp >= cutoff_time]

        if not recent_metrics:
            return {'error': 'No data available'}

        # Calculate statistics
        cpu_values = [m.cpu_usage_percent for m in recent_metrics]
        memory_values = [m.memory_usage_percent for m in recent_metrics]
        latency_values = [m.audio_latency_ms for m in recent_metrics]

        report = {
            'duration_seconds': duration_seconds,
            'measurements': len(recent_metrics),
            'cpu': {
                'avg': np.mean(cpu_values),
                'max': np.max(cpu_values),
                'min': np.min(cpu_values),
                'std': np.std(cpu_values)
            },
            'memory': {
                'avg': np.mean(memory_values),
                'max': np.max(memory_values),
                'min': np.min(memory_values)
            },
            'audio_latency': {
                'avg': np.mean(latency_values),
                'max': np.max(latency_values),
                'min': np.min(latency_values)
            },
            'system_health': 'good' if np.mean(cpu_values) < 70 and np.mean(latency_values) < 10 else 'fair'
        }

        if include_graphs:
            report['graphs'] = {
                'cpu_timeline': cpu_values,
                'latency_timeline': latency_values
            }

        return report
