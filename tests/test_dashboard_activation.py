import pytest

from velacare.dashboard.activation import (
    ActivationState,
    DisabledActivationProvider,
    MockActivationProvider,
    activation_provider_for_mode,
)


def test_disabled_activation_is_default_and_never_accepts_a_start():
    provider = activation_provider_for_mode("disabled")
    assert isinstance(provider, DisabledActivationProvider)
    status = provider.get_status()
    assert status.status == ActivationState.UNKNOWN
    assert status.enabled is False
    result = provider.request_start({}, "no-remote-call")
    assert result.accepted is False
    assert result.status == ActivationState.UNAVAILABLE


def test_mock_activation_simulates_stopped_starting_running_ready_and_idempotency():
    provider = MockActivationProvider()
    assert provider.get_status().status == ActivationState.STOPPED

    accepted = provider.request_start({}, "request-001")
    assert accepted.accepted is True
    assert accepted.status == ActivationState.STARTING
    assert accepted.simulated is True
    assert provider.request_start({}, "request-001") == accepted
    assert provider.get_status().status == ActivationState.RUNNING
    assert provider.get_status().status == ActivationState.READY


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("auth_required", ActivationState.AUTH_REQUIRED),
        ("error", ActivationState.ERROR),
    ],
)
def test_mock_activation_simulates_authorization_and_failure(scenario, expected):
    provider = MockActivationProvider(scenario)
    result = provider.request_start({}, f"request-{scenario}")
    assert result.accepted is False
    assert result.status == expected
    assert result.simulated is True
    assert provider.get_status().status == expected


def test_mock_activation_simulates_timeout():
    provider = MockActivationProvider("timeout")
    assert provider.request_start({}, "request-timeout").status == ActivationState.STARTING
    assert provider.get_status().status == ActivationState.STARTING
    assert provider.get_status().status == ActivationState.ERROR


def test_activation_provider_rejects_unconfigured_modes():
    with pytest.raises(ValueError, match="disabled.*mock"):
        activation_provider_for_mode("http")
