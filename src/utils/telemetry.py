"""OpenTelemetry tracing setup for distributed tracing."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .logging_config import get_logger

logger = get_logger(__name__)


def setup_telemetry(
    service_name: str = "trinav",
    otlp_endpoint: str | None = None
) -> trace.Tracer | None:
    """Setup OpenTelemetry tracing with OTLP export.

    Args:
        service_name: Name of the service
        otlp_endpoint: OTLP endpoint (e.g., http://localhost:4317)

    Returns:
        Configured tracer or None if tracing disabled
    """
    if not otlp_endpoint:
        logger.info("OpenTelemetry tracing disabled (no OTLP endpoint configured)")
        return None

    try:
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: service_name
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Create OTLP span exporter
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        logger.info(f"OpenTelemetry tracing enabled: {otlp_endpoint}")
        return trace.get_tracer(__name__)

    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry tracing: {e}")
        return None


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance.

    Returns:
        Tracer instance
    """
    return trace.get_tracer(__name__)
