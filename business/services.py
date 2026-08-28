# business/services.py


from inventory.services import get_inventory_stats
from customers.services import get_client_stats
from documents.services import get_invoice_stats
import re
import logging

import cloudinary
import cloudinary.uploader
from django.conf import settings

logger = logging.getLogger(__name__)

cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE["CLOUD_NAME"],
    api_key=settings.CLOUDINARY_STORAGE["API_KEY"],
    api_secret=settings.CLOUDINARY_STORAGE["API_SECRET"],
    secure=True,
)

_PUBLIC_ID_RE = re.compile(r'/upload/v\d+/(?P<public_id>.+?)\.[a-zA-Z0-9]+$')

def extract_cloudinary_public_id(url: str) -> str | None:
    """
    Pulls the public_id back out of a Cloudinary secure_url. Reliable here
    specifically because /api/cloudinary/signature/ always assigns an
    explicit public_id (folder/user_timestamp) — Cloudinary preserves it
    verbatim rather than auto-generating one, so this isn't guessing.
    """
    if not url:
        return None
    match = _PUBLIC_ID_RE.search(url)
    return match.group('public_id') if match else None


def delete_cloudinary_asset(url: str) -> None:
    """
    Best-effort cleanup of a replaced/removed logo or signature image.
    Never raises — a Cloudinary failure here must not break the caller's
    actual save. Worst case, an asset is orphaned and cleaned up later.
    """
    public_id = extract_cloudinary_public_id(url)
    if not public_id:
        return
    try:
        cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception:
        logger.warning("Failed to delete orphaned Cloudinary asset: %s", public_id, exc_info=True)

def get_full_summary_data(business):
    return {
        "stats": {
            "inventory": get_inventory_stats(business.id),
            "clients": get_client_stats(business.id),
            "invoices": get_invoice_stats(business.id),
        }
    }
 