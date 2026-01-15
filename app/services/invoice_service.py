from pathlib import Path
from typing import Optional

INVOICE_DIR = Path("invoices")


def invoice_exists(order_id: int) -> bool:
    """Check if invoice PDF exists"""
    invoice_path = INVOICE_DIR / f"invoice_{order_id}.pdf"
    return invoice_path.exists()


def load_invoice_pdf(order_id: int) -> Optional[bytes]:
    """
    Load invoice PDF if it exists.
    Returns None if invoice not found (DO NOT raise).
    """
    invoice_path = INVOICE_DIR / f"invoice_{order_id}.pdf"

    if not invoice_path.exists():
        return None

    return invoice_path.read_bytes()
