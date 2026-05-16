import re
import logging
from sqlalchemy.orm import Session
from models import Device

logger = logging.getLogger(__name__)

# Simpel MAC-validering: accepterer xx:xx:xx:xx:xx:xx og xx-xx-xx-xx-xx-xx
_MAC_RE = re.compile(r"^([0-9a-f]{2}[:\-]){5}[0-9a-f]{2}$", re.IGNORECASE)

CLI_MAC = "00:00:00:00:00:00"   # Reserveret MAC til CLI-testklient


def is_valid_mac(mac: str) -> bool:
    return bool(_MAC_RE.match(mac))


def get_or_create_device(db: Session, mac: str, name: str = "") -> Device:
    """
    Hent eksisterende enhed eller opret en ny (auto-registrering).
    Returnerer Device-objektet.
    """
    mac = mac.lower().replace("-", ":")

    device = db.query(Device).filter(Device.mac_address == mac).first()
    if device:
        logger.info(f"Kendt enhed: {mac} ({device.name})")
        return device

    # Første gang — auto-registrér
    device = Device(
        mac_address=mac,
        name=name or _default_name(mac),
        elo=800,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    logger.info(f"Ny enhed registreret: {mac} → '{device.name}'")
    return device


def _default_name(mac: str) -> str:
    """Generer et standard-navn fra de sidste 3 bytes af MAC-adressen."""
    suffix = mac.replace(":", "")[-6:].upper()
    return f"device-{suffix}"
