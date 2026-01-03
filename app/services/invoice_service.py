from pathlib import Path

INVOICE_DIR = Path("invoices")

def load_invoice_pdf(order_id: int) -> bytes:
    invoice_path = INVOICE_DIR / f"invoice_{order_id}.pdf"

    if not invoice_path.exists():
        raise FileNotFoundError(f"Invoice not found for order {order_id}")

    return invoice_path.read_bytes()
