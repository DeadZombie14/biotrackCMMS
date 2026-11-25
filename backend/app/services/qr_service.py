import io
import qrcode
import qrcode.image.svg


def generate_qr_svg(url: str) -> str:
    """Generate a crisp scalable SVG QR code for the physical maintenance sticker (AD-08)."""
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(url, image_factory=factory, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")
