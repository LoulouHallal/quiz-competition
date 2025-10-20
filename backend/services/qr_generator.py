import qrcode
import qrcode.image.svg
import os
from config import Config

class QRGenerator:
    @staticmethod
    def generate_qr(data, filename, format='svg'):
        """Generate QR code for session join link."""
        qr_path = os.path.join(Config.QR_CODE_DIR, filename)
        
        if format == 'svg':
            factory = qrcode.image.svg.SvgPathImage
            img = qrcode.make(data, image_factory=factory, box_size=10)
            img.save(qr_path)
        else:
            img = qrcode.make(data, box_size=10, border=2)
            img.save(qr_path)
        
        return qr_path
    
    @staticmethod
    def generate_session_qr(session_code):
        """Generate QR code for a session."""
        join_url = f"{Config.PUBLIC_BASE_URL}/join?code={session_code}"
        filename = f"{session_code}.svg"
        qr_path = QRGenerator.generate_qr(join_url, filename, format='svg')
        
        # Return relative URL for serving
        return f"/static/qr/{filename}"
