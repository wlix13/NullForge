"""Monitoring agent deployment module."""

from pyinfra.context import host

from nullforge.molds import FeaturesMold, MonitoringMold
from nullforge.molds.monitoring import NezhaBackend
from nullforge.smithy.monitoring.nezha.deploy import deploy_nezha


def deploy_monitoring() -> None:
    """Deploy configured monitoring agent."""

    features: FeaturesMold = host.data.features
    monitoring: MonitoringMold = features.monitoring

    match monitoring.backend:
        case NezhaBackend():
            deploy_nezha(monitoring.backend)


deploy_monitoring()
