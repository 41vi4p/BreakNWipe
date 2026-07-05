"""
Device Health & Lifespan Module

Surfaces SMART health, temperature, and (where a reliable source exists) an
expected-lifespan-remaining estimate for a storage device.

Deliberately honest about what can and can't be estimated: NVMe drives report
a standardized "percentage_used" wear indicator per spec (already parsed by
NVMeDevice.get_smart_data), and some SATA/USB SSDs expose a vendor-specific
wear attribute via SMART -- but plenty of drives (essentially all HDDs, and
SSDs without a recognized wear attribute) have no reliable universal
"remaining lifespan" metric at all. Rather than fabricate a number for those,
this module reports `lifespan_remaining_percent = None` with a `lifespan_source`
explaining why, alongside whatever raw health indicators are available
(power-on hours, reallocated/pending sector counts) as an honest substitute.
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .storage import StorageDevice, DeviceInterface
from .nvme import NVMeDevice

logger = logging.getLogger(__name__)

# SATA/USB SMART attributes (by the name smartctl reports them under) that
# vendors use to expose a wear/life-remaining indicator, in order of
# preference. Value is normalized 0-100 already for all of these (as opposed
# to their RAW_VALUE, which is vendor-specific and not comparable) -- so these
# are read from the VALUE column, not RAW_VALUE, unlike the other attributes
# below.
_WEAR_ATTRIBUTES = [
    "SSD_Life_Left",
    "Percent_Lifetime_Remain",
    "Media_Wearout_Indicator",
    "Wear_Leveling_Count",
]

# Raw-value health-indicator attributes, always surfaced when present since
# they're standard across SATA/SSD/HDD and don't require interpretation.
_RAW_ATTRIBUTES = {
    "power_on_hours": "Power_On_Hours",
    "power_cycles": "Power_Cycle_Count",
    "reallocated_sectors": "Reallocated_Sector_Ct",
    "pending_sectors": "Current_Pending_Sector",
}


@dataclass
class DeviceHealth:
    """Health/lifespan snapshot for a storage device."""

    smart_overall: Optional[str] = None            # "PASSED" / "FAILED" / None if unavailable
    temperature_celsius: Optional[int] = None
    power_on_hours: Optional[int] = None
    power_cycles: Optional[int] = None
    reallocated_sectors: Optional[int] = None
    pending_sectors: Optional[int] = None
    lifespan_remaining_percent: Optional[int] = None
    lifespan_source: str = "not available"
    warnings: List[str] = field(default_factory=list)
    raw_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "smart_overall": self.smart_overall,
            "temperature_celsius": self.temperature_celsius,
            "power_on_hours": self.power_on_hours,
            "power_cycles": self.power_cycles,
            "reallocated_sectors": self.reallocated_sectors,
            "pending_sectors": self.pending_sectors,
            "lifespan_remaining_percent": self.lifespan_remaining_percent,
            "lifespan_source": self.lifespan_source,
            "warnings": self.warnings,
            "raw_attributes": self.raw_attributes,
        }


def get_device_health(device: StorageDevice) -> DeviceHealth:
    """Collect a health/lifespan snapshot for device, honest about what can't be estimated."""
    if device.interface == DeviceInterface.NVME:
        return _get_nvme_health(device)
    return _get_sata_health(device)


def _get_nvme_health(device: StorageDevice) -> DeviceHealth:
    """
    NVMe reports a standardized wear indicator (percentage_used, 0-100+ per
    the NVMe spec, 100 = has reached its rated endurance) -- reuse the
    existing, already-tested parser rather than re-implementing it.
    """
    health = DeviceHealth()
    try:
        smart_data = NVMeDevice().get_smart_data(device)
    except Exception as e:
        logger.debug(f"Failed to get NVMe health for {device.path}: {e}")
        smart_data = {}

    health.raw_attributes = smart_data
    health.temperature_celsius = smart_data.get("temperature")
    health.power_on_hours = smart_data.get("power_on_hours")
    health.power_cycles = smart_data.get("power_cycles")

    percentage_used = smart_data.get("percentage_used")
    if percentage_used is not None:
        health.lifespan_remaining_percent = max(0, 100 - int(percentage_used))
        health.lifespan_source = "NVMe standardized wear indicator (percentage_used)"
        if percentage_used >= 100:
            health.warnings.append(
                f"Drive has reached its rated endurance (percentage_used={percentage_used}%)"
            )
        elif percentage_used >= 90:
            health.warnings.append(f"Drive nearing rated endurance ({percentage_used}% used)")

    critical_warning = smart_data.get("critical_warning")
    if critical_warning:
        health.smart_overall = "FAILED"
        health.warnings.append(f"NVMe reports a critical warning (code {critical_warning})")
    elif percentage_used is not None:
        health.smart_overall = "PASSED"

    return health


def _get_sata_health(device: StorageDevice) -> DeviceHealth:
    """
    SATA/USB SSDs sometimes expose a vendor-specific wear attribute (not
    standardized -- absent on plenty of drives); HDDs have no reliable
    universal lifespan metric at all. Only claim a percentage when a
    recognized attribute is actually present.
    """
    health = DeviceHealth()

    try:
        result = subprocess.run(
            ["smartctl", "-A", device.path], capture_output=True, text=True, timeout=15,
        )
        output = result.stdout
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        logger.debug(f"Failed to run smartctl -A for {device.path}: {e}")
        output = ""

    try:
        health_result = subprocess.run(
            ["smartctl", "-H", device.path], capture_output=True, text=True, timeout=15,
        )
        if "PASSED" in health_result.stdout:
            health.smart_overall = "PASSED"
        elif "FAILED" in health_result.stdout:
            health.smart_overall = "FAILED"
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
        logger.debug(f"Failed to run smartctl -H for {device.path}: {e}")

    for field_name, attr_name in _RAW_ATTRIBUTES.items():
        value = _extract_smart_raw_value(output, attr_name)
        if value is not None:
            setattr(health, field_name, value)
            health.raw_attributes[attr_name] = value

    for attr_name in _WEAR_ATTRIBUTES:
        value = _extract_smart_normalized_value(output, attr_name)
        if value is not None:
            health.lifespan_remaining_percent = value
            health.lifespan_source = f"vendor SSD SMART attribute ({attr_name})"
            health.raw_attributes[attr_name] = value
            break
    else:
        health.lifespan_source = (
            "not available -- no standardized wear indicator for this drive "
            "(common for HDDs, and SSDs that don't expose a recognized SMART "
            "wear attribute); see power-on hours / reallocated sectors instead"
        )

    if health.reallocated_sectors and health.reallocated_sectors > 0:
        health.warnings.append(f"{health.reallocated_sectors} reallocated sector(s) reported")
    if health.pending_sectors and health.pending_sectors > 0:
        health.warnings.append(f"{health.pending_sectors} pending (unstable) sector(s) reported")
    if health.smart_overall == "FAILED":
        health.warnings.append("SMART overall-health self-assessment: FAILED")
    if health.lifespan_remaining_percent is not None and health.lifespan_remaining_percent <= 10:
        health.warnings.append(
            f"Estimated {health.lifespan_remaining_percent}% of rated life remaining"
        )

    return health


def _extract_smart_raw_value(output: str, attribute_name: str) -> Optional[int]:
    """Extract an attribute's RAW_VALUE column from `smartctl -A` output."""
    match = re.search(
        rf"{attribute_name}\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\d+)", output,
    )
    return int(match.group(1)) if match else None


def _extract_smart_normalized_value(output: str, attribute_name: str) -> Optional[int]:
    """
    Extract an attribute's normalized VALUE column (0-100) from `smartctl -A`
    output -- this is the 3rd field after the attribute name (FLAG, VALUE),
    not the RAW_VALUE at the end, since wear indicators are only meaningfully
    comparable in their normalized form.
    """
    match = re.search(rf"{attribute_name}\s+\S+\s+(\d+)\s+\d+\s+\d+", output)
    return int(match.group(1)) if match else None
