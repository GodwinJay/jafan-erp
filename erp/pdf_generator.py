"""
PDF Generator for Jafan ERP
Professional Branded Documents with Logo
Generates: Invoices, Waybills, Receipts, Customer Statements, Proforma Invoices

Brand Colors:
- Deep Navy Blue: #254451
- Metallic Gold: #D4AF37  
- Off-White/Cream: #FEFCF7
"""
import io
import os
from decimal import Decimal
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Circle, Rect, String, Line
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.graphics import renderPDF


# ==============================================================================
# FONT REGISTRATION FOR NAIRA SYMBOL
# ==============================================================================
FONT_REGISTERED = False
UNICODE_FONT = 'Helvetica'
UNICODE_FONT_BOLD = 'Helvetica-Bold'

def register_unicode_font():
    """Register Unicode-compatible fonts for Naira symbol."""
    global FONT_REGISTERED, UNICODE_FONT, UNICODE_FONT_BOLD
    
    if FONT_REGISTERED:
        return UNICODE_FONT
    
    font_paths = [
        # Linux (Railway/Ubuntu) - Most likely to work
        ('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        # Alternative Linux paths
        ('DejaVuSans', '/usr/share/fonts/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf'),
        # Windows
        ('Arial', 'C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
        ('Calibri', 'C:/Windows/Fonts/calibri.ttf', 'C:/Windows/Fonts/calibrib.ttf'),
        ('DejaVuSans', 'C:/Windows/Fonts/DejaVuSans.ttf', 'C:/Windows/Fonts/DejaVuSans-Bold.ttf'),
    ]
    
    for font_name, regular_path, bold_path in font_paths:
        try:
            if os.path.exists(regular_path):
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
                UNICODE_FONT = font_name
                
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(f'{font_name}-Bold', bold_path))
                    UNICODE_FONT_BOLD = f'{font_name}-Bold'
                else:
                    UNICODE_FONT_BOLD = font_name  # Use regular if bold not found
                
                FONT_REGISTERED = True
                print(f"✅ Registered Unicode font: {font_name}")
                return font_name
        except Exception as e:
            print(f"⚠️ Failed to register {font_name}: {e}")
            continue
    
    # Fallback - use Helvetica but replace ₦ with "NGN"
    print("⚠️ No Unicode font found, using Helvetica fallback")
    FONT_REGISTERED = True
    return 'Helvetica'

register_unicode_font()



# ==============================================================================
# BRAND COLORS
# ==============================================================================

NAVY_BLUE = colors.HexColor("#254451")
GOLD = colors.HexColor("#D4AF37")
CREAM = colors.HexColor("#FEFCF7")
LIGHT_GOLD = colors.HexColor("#F5E6C8")
LIGHT_NAVY = colors.HexColor("#E8EDEF")


# ==============================================================================
# COMPANY INFO
# ==============================================================================

COMPANY_NAME = "JAFAN STANDARD BLOCK INDUSTRY"
COMPANY_TAGLINE = "A Division of GC. OKOLI ENTERPRISES"
COMPANY_ADDRESS = "KM2 Otukpo-Makurdi Road, Ikobi Village, Otukpo, Benue State"
COMPANY_PHONE = "+234 706 392 8346"
COMPANY_EMAIL = "godwinjay08@gmail.com"


# ==============================================================================
# LOGO GENERATOR (Simplified Vector Version)
# ==============================================================================

def create_logo_drawing(width=60*mm, height=25*mm):
    """
    Create a simplified version of the Jafan logo using ReportLab drawing.
    This creates a professional placeholder until actual logo is uploaded.
    """
    d = Drawing(width, height)
    
    # Background circle (seal style)
    center_x = height / 2
    center_y = height / 2
    radius = height / 2 - 2*mm
    
    # Outer ring
    d.add(Circle(center_x, center_y, radius, fillColor=NAVY_BLUE, strokeColor=NAVY_BLUE))
    d.add(Circle(center_x, center_y, radius - 2*mm, fillColor=CREAM, strokeColor=CREAM))
    
    # Inner circle
    d.add(Circle(center_x, center_y, radius - 4*mm, fillColor=NAVY_BLUE, strokeColor=NAVY_BLUE))
    
    # Gold checkmark (simplified)
    d.add(Line(center_x - 4*mm, center_y, center_x - 1*mm, center_y - 3*mm, strokeColor=GOLD, strokeWidth=2))
    d.add(Line(center_x - 1*mm, center_y - 3*mm, center_x + 5*mm, center_y + 4*mm, strokeColor=GOLD, strokeWidth=2))
    
    # Company name text next to logo (Optional fallback if image fails)
    
    return d


def get_logo_with_fallback(logo_path=None, width=60*mm, height=25*mm):
    """
    Try to load actual logo, fall back to generated version.
    Place your logo at: static/images/jafan_logo.png
    """
    if logo_path and os.path.exists(logo_path):
        try:
            return Image(logo_path, width=width, height=height)
        except Exception:
            pass
    
    # Return the drawing-based logo
    return create_logo_drawing(width, height)


# ==============================================================================
# BASE PDF GENERATOR
# ==============================================================================

class PDFGenerator:
    """Base PDF Generator with Jafan branding."""
    
    def __init__(self):
        self.font_name = register_unicode_font()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        # Try to find logo
        self.logo_path = None
        possible_paths = [
            'static/images/jafan_logo.png',
            'erp/static/images/jafan_logo.png',
            'media/jafan_logo.png',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                self.logo_path = path
                break
    
    def _setup_custom_styles(self):
        """Setup branded paragraph styles."""
        
        # Company Name Style
        self.styles.add(ParagraphStyle(
            name='CompanyName',
            fontName=UNICODE_FONT_BOLD,
            fontSize=14,
            textColor=NAVY_BLUE,
            alignment=TA_CENTER,
            spaceAfter=2
        ))
        
        # Tagline Style
        self.styles.add(ParagraphStyle(
            name='Tagline',
            fontName=UNICODE_FONT,
            fontSize=9,
            textColor=GOLD,
            alignment=TA_CENTER,
            spaceAfter=4
        ))
        
        # Document Title
        self.styles.add(ParagraphStyle(
            name='DocTitle',
            fontName=UNICODE_FONT_BOLD,
            fontSize=16,
            textColor=NAVY_BLUE,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=10
        ))
        
        # Section Header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            fontName=UNICODE_FONT_BOLD,
            fontSize=10,
            textColor=NAVY_BLUE,
            spaceBefore=8,
            spaceAfter=4
        ))
        
        # Normal Text
        self.styles.add(ParagraphStyle(
            name='NormalText',
            fontName=UNICODE_FONT,
            fontSize=9,
            textColor=colors.black,
            spaceAfter=3
        ))
        
        # Small Text
        self.styles.add(ParagraphStyle(
            name='SmallText',
            fontName=UNICODE_FONT,
            fontSize=7,
            textColor=colors.gray
        ))
        
        # Amount Large
        self.styles.add(ParagraphStyle(
            name='AmountLarge',
            fontName=UNICODE_FONT_BOLD,
            fontSize=18,
            textColor=NAVY_BLUE,
            alignment=TA_CENTER
        ))
        
        # Center Align
        self.styles.add(ParagraphStyle(
            name='CenterAlign',
            fontName=UNICODE_FONT,
            fontSize=9,
            alignment=TA_CENTER
        ))
        
        # Right Align
        self.styles.add(ParagraphStyle(
            name='RightAlign',
            fontName=UNICODE_FONT,
            fontSize=9,
            alignment=TA_RIGHT
        ))
        
        # Footer
        self.styles.add(ParagraphStyle(
            name='Footer',
            fontName=UNICODE_FONT,
            fontSize=8,
            textColor=NAVY_BLUE,
            alignment=TA_CENTER
        ))
    
    def _get_branded_header(self, width_override=None):
        """
        Generate professional branded header.
        Layout: Logo (Left) | Name/Tagline (Left)
                Address & Contact (Centered Below)
        """
        elements = []
        # Default A4 usable width if not provided
        doc_width = width_override if width_override else A4[0] - 30*mm 
        
        # 1. Get Logo - BOLDER SIZE (increased to 35mm)
        logo_size = 35*mm
        logo = get_logo_with_fallback(self.logo_path, width=logo_size, height=logo_size)
        
        # 2. Styles
        header_title_style = ParagraphStyle(
            'HeaderTitle', parent=self.styles['Normal'], 
            fontName=UNICODE_FONT_BOLD, fontSize=11, textColor=NAVY_BLUE, leading=13
        )
        header_sub_style = ParagraphStyle(
            'HeaderSub', parent=self.styles['Normal'], 
            fontName=UNICODE_FONT, fontSize=8, textColor=GOLD, leading=10
        )
        header_center_style = ParagraphStyle(
            'HeaderCenter', parent=self.styles['Normal'], 
            fontName=UNICODE_FONT, fontSize=9, textColor=NAVY_BLUE, leading=12,
            alignment=TA_CENTER
        )

        # 3. Top Section: [Logo | Text]
        company_details_left = [
            Paragraph(COMPANY_NAME, header_title_style),
            Paragraph(COMPANY_TAGLINE, header_sub_style),
        ]

        # Table with Logo on left, text on right. Adjusted colWidths for bigger logo.
        header_data = [[logo, company_details_left]]
        # Give logo column slightly more room than the image size
        col1_width = logo_size + 5*mm 
        header_table = Table(header_data, colWidths=[col1_width, doc_width - col1_width])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        
        # 4. Bottom Section: Address (Centered)
        # Reduced spacer for tighter fit
        elements.append(Spacer(1, 1*mm)) 
        elements.append(Paragraph(COMPANY_ADDRESS, header_center_style))
        elements.append(Paragraph(f"Tel: {COMPANY_PHONE} | Email: {COMPANY_EMAIL}", header_center_style))
        
        # 5. Gold Line separator
        # Reduced spacer for tighter fit
        elements.append(Spacer(1, 1*mm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceBefore=1, spaceAfter=1))
        # Reduced spacer for tighter fit
        elements.append(Spacer(1, 2*mm))
        
        return elements
    
    def _get_footer(self):
        """Generate branded footer."""
        elements = []
        
        # Reduced space before footer
        elements.append(HRFlowable(
            width="100%", thickness=1, color=NAVY_BLUE,
            spaceBefore=5, spaceAfter=3
        ))
        elements.append(Paragraph(
            "Thank you for your patronage! | Quality is our Standard",
            self.styles['Footer']
        ))
        elements.append(Paragraph(
            f"Tel: {COMPANY_PHONE} | {COMPANY_EMAIL}",
            self.styles['SmallText']
        ))
        
        return elements
    
    def _format_currency(self, amount):
        """Format as Nigerian Naira."""
        if amount is None:
            amount = Decimal('0')

        if UNICODE_FONT != 'Helvetica':
            return f"₦{amount:,.2f}"
        else:
            return f"NGN{amount:,.2f}"
    
    def _amount_in_words(self, amount):
        """Convert amount to words (simplified)."""
        amount = int(amount)
        if amount == 0:
            return "Zero Naira Only"
        
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
                'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
                'Seventeen', 'Eighteen', 'Nineteen']
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
        
        def words(n):
            if n < 20:
                return ones[n]
            elif n < 100:
                return tens[n // 10] + (' ' + ones[n % 10] if n % 10 else '')
            elif n < 1000:
                return ones[n // 100] + ' Hundred' + (' and ' + words(n % 100) if n % 100 else '')
            elif n < 1000000:
                return words(n // 1000) + ' Thousand' + (' ' + words(n % 1000) if n % 1000 else '')
            else:
                return words(n // 1000000) + ' Million' + (' ' + words(n % 1000000) if n % 1000000 else '')
        
        return words(amount) + " Naira Only"
    
    def _create_response(self, buffer, filename):
        """Create HTTP response."""
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    
    def _get_base_table_style(self):
        """Base table style with branding."""
        return [
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Slightly reduced padding for A5 fit
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]


# ==============================================================================
# INVOICE GENERATOR
# ==============================================================================

class InvoiceGenerator(PDFGenerator):
    """Generate professional branded Invoice on A5."""
    
    def generate(self, supply_log):
        buffer = io.BytesIO()
        # Tighter margins for A5 single page fit
        doc = SimpleDocTemplate(
            buffer, pagesize=A5,
            topMargin=6*mm, bottomMargin=6*mm,
            leftMargin=8*mm, rightMargin=8*mm
        )
        elements = []
        
        # Header - Use Branded Header (Scaled for A5 width)
        elements.extend(self._get_branded_header(width_override=doc.width))
        
        # Document Title with Navy Background
        title_table = Table(
            [['INVOICE / DELIVERY NOTE']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            # Reduced padding
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(title_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Invoice Info Box
        invoice_data = [
            ['Invoice No:', f'INV-{supply_log.pk:05d}', 'Date:', supply_log.date.strftime('%d/%m/%Y')],
            ['Type:', supply_log.get_delivery_type_display(), 'Time:', timezone.now().strftime('%H:%M')],
        ]
        invoice_table = Table(invoice_data, colWidths=[45, 75, 35, 55])
        invoice_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('TEXTCOLOR', (2, 0), (2, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
        ]))
        elements.append(invoice_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Customer Section
        elements.append(Paragraph("BILL TO:", self.styles['SectionHeader']))
        customer_data = [
            ['Customer:', supply_log.customer.name],
            ['Phone:', supply_log.customer.phone],
            ['Site:', supply_log.site.name],
            ['Address:', supply_log.site.address[:50] + '...' if len(supply_log.site.address) > 50 else supply_log.site.address],
        ]
        customer_table = Table(customer_data, colWidths=[45, 165])
        customer_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(customer_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Products Table
        elements.append(Paragraph("ITEMS:", self.styles['SectionHeader']))
        
        # Shorten block type name if too long
        block_name = supply_log.block_type.name
        if len(block_name) > 12:
            block_name = block_name[:11] + '..'
        
        product_data = [
            ['Description', 'Qty', 'Brk', 'Del', 'Price', 'Amount'],
            [
                block_name,
                str(supply_log.quantity_loaded),
                str(supply_log.breakages),
                str(supply_log.quantity_delivered),
                self._format_currency(supply_log.unit_price),
                self._format_currency(supply_log.quantity_delivered * supply_log.unit_price)
            ],
        ]
        
        if supply_log.logistics_discount > 0:
            product_data.append(['', '', '', '', 'Discount:', f'-{self._format_currency(supply_log.logistics_discount)}'])
        
        product_table = Table(product_data, colWidths=[55, 30, 25, 30, 40, 51])
        product_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, 0), 1, NAVY_BLUE),
            ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.gray),
        ]))
        elements.append(product_table)
        
        # Total Box (Gold accent)
        total_data = [
            ['TOTAL:', self._format_currency(supply_log.total_value)],
        ]
        total_table = Table(total_data, colWidths=[160, 71])
        total_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TEXTCOLOR', (0, 0), (-1, -1), NAVY_BLUE),
            ('BACKGROUND', (1, 0), (1, -1), LIGHT_GOLD),
            ('BOX', (1, 0), (1, -1), 1.5, GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(Spacer(1, 2*mm))
        elements.append(total_table)
        
        # Logistics Info
        if supply_log.delivery_type == 'DELIVERED' and supply_log.truck:
            elements.append(Spacer(1, 2*mm))
            logistics_data = [
                ['Truck:', supply_log.truck.name, 'Driver:', supply_log.driver.name if supply_log.driver else 'N/A'],
            ]
            logistics_table = Table(logistics_data, colWidths=[35, 80, 35, 60])
            logistics_table.setStyle(TableStyle([
                *self._get_base_table_style(),
                ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
                ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ]))
            elements.append(logistics_table)
        
        if supply_log.delivery_type == 'SELF_PICKUP' and supply_log.pickup_authorized_by:
            elements.append(Spacer(1, 2*mm))
            elements.append(Paragraph(
                f"<b>Pickup Authorized By:</b> {supply_log.pickup_authorized_by}",
                self.styles['NormalText']
            ))
        
        elements.append(Spacer(1, 2*mm))
        
        # Balance Info
        balance_text = f"Account Balance: {self._format_currency(supply_log.customer.account_balance)}"
        if supply_log.customer.balance_status == "Owes":
            balance_text += " (OUTSTANDING)"
        elements.append(Paragraph(balance_text, self.styles['RightAlign']))
        
        # Signatures
        elements.append(Spacer(1, 5*mm)) # Reduced spacer
        sig_data = [
            ['____________________', '____________________'],
            ['Customer Signature', 'Authorized Signature'],
        ]
        sig_table = Table(sig_data, colWidths=[105, 105])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, 1), UNICODE_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.gray),
            ('TOPPADDING', (0, 1), (-1, 1), 2),
        ]))
        elements.append(sig_table)
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        return self._create_response(buffer, f'Invoice_INV-{supply_log.pk:05d}.pdf')


# ==============================================================================
# WAYBILL GENERATOR
# ==============================================================================

class WaybillGenerator(PDFGenerator):
    """Generate professional branded Waybill on A4."""
    
    def generate(self, supply_log):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=10*mm, bottomMargin=10*mm,
            leftMargin=15*mm, rightMargin=15*mm
        )
        elements = []
        
        # Header - Use Branded Header
        elements.extend(self._get_branded_header())
        
        # Document Title
        title_table = Table(
            [['WAYBILL / DELIVERY TICKET']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 3*mm))
        
        # Waybill Info
        waybill_data = [
            ['Waybill No:', f'WB-{supply_log.pk:05d}', 'Date:', supply_log.date.strftime('%d/%m/%Y')],
        ]
        waybill_table = Table(waybill_data, colWidths=[70, 120, 50, 100])
        waybill_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('FONTSIZE', (1, 0), (1, -1), 14),
            ('TEXTCOLOR', (1, 0), (1, -1), NAVY_BLUE),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(waybill_table)
        elements.append(Spacer(1, 4*mm))
        
        # Delivery Info (Highlighted - Most Important)
        elements.append(Paragraph("📍 DELIVER TO:", self.styles['SectionHeader']))
        
        delivery_data = [
            ['Customer:', supply_log.customer.name],
            ['Phone:', supply_log.customer.phone],
            ['Site:', supply_log.site.name],
            ['Address:', supply_log.site.address],
        ]
        if supply_log.site.contact_person:
            delivery_data.append(['Contact:', f"{supply_log.site.contact_person} ({supply_log.site.contact_phone or 'N/A'})"])
        
        delivery_table = Table(delivery_data, colWidths=[70, 290])
        delivery_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('FONTSIZE', (1, 2), (1, 2), 12),  # Site name larger
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
            ('BOX', (0, 0), (-1, -1), 2, GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(delivery_table)
        elements.append(Spacer(1, 4*mm))
        
        # Cargo (Large and Bold)
        elements.append(Paragraph("📦 CARGO:", self.styles['SectionHeader']))
        
        cargo_data = [
            ['Product', 'Quantity Loaded'],
            [supply_log.block_type.name, str(supply_log.quantity_loaded)],
        ]
        cargo_table = Table(cargo_data, colWidths=[240, 120])
        cargo_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, 1), 16),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 2, NAVY_BLUE),
            ('GRID', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(cargo_table)
        elements.append(Spacer(1, 4*mm))
        
        # Vehicle & Driver
        elements.append(Paragraph("🚚 VEHICLE & DRIVER:", self.styles['SectionHeader']))
        vehicle_data = [
            ['Truck:', supply_log.truck.name if supply_log.truck else 'N/A', 
             'Plate:', supply_log.truck.plate_number if supply_log.truck else 'N/A'],
            ['Driver:', supply_log.driver.name if supply_log.driver else 'N/A', 
             'Phone:', supply_log.driver.phone if supply_log.driver else 'N/A'],
        ]
        vehicle_table = Table(vehicle_data, colWidths=[50, 130, 45, 135])
        vehicle_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(vehicle_table)
        elements.append(Spacer(1, 5*mm))
        
        # Delivery Confirmation Section - Fixed alignment
        elements.append(Paragraph("✍️ DELIVERY CONFIRMATION (To be completed at site):", self.styles['SectionHeader']))
        
        confirm_data = [
            ['Quantity Delivered: __________', 'Breakages: __________'],
            ['Received By: _____________________', 'Phone: ______________'],
            ['Signature: _____________________', 'Date/Time: ___________'],
        ]
        confirm_table = Table(confirm_data, colWidths=[180, 180])
        confirm_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1.5, NAVY_BLUE),
            ('BACKGROUND', (0, 0), (-1, -1), CREAM),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(confirm_table)
        elements.append(Spacer(1, 4*mm))
        
        # Driver Instructions
        elements.append(Paragraph("📋 DRIVER INSTRUCTIONS:", self.styles['SectionHeader']))
        instructions_data = [
            ['1.', 'Count blocks with customer BEFORE offloading'],
            ['2.', 'Record any breakages discovered during transit'],
            ['3.', 'Get customer signature AFTER successful delivery'],
            ['4.', 'Return this waybill to office immediately after delivery'],
        ]
        instructions_table = Table(instructions_data, colWidths=[20, 340])
        instructions_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), GOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(instructions_table)
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        return self._create_response(buffer, f'Waybill_WB-{supply_log.pk:05d}.pdf')


# ==============================================================================
# RECEIPT GENERATOR
# ==============================================================================

class ReceiptGenerator(PDFGenerator):
    """Generate professional branded Receipt on A5."""
    
    def generate(self, payment):
        buffer = io.BytesIO()
        # Tighter margins for A5 single page fit
        doc = SimpleDocTemplate(
            buffer, pagesize=A5,
            topMargin=6*mm, bottomMargin=6*mm,
            leftMargin=8*mm, rightMargin=8*mm
        )
        elements = []
        
        # Header - Use Branded Header (Scaled for A5 width)
        elements.extend(self._get_branded_header(width_override=doc.width))
        
        # Document Title
        title_table = Table(
            [['OFFICIAL RECEIPT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            # Reduced padding
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(title_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Receipt Info
        receipt_data = [
            ['Receipt No:', f'RCP-{payment.pk:05d}'],
            ['Date:', payment.date.strftime('%d/%m/%Y')],
        ]
        receipt_table = Table(receipt_data, colWidths=[70, 140])
        receipt_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (1, 0), (1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elements.append(receipt_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Received From
        elements.append(Paragraph("RECEIVED FROM:", self.styles['SectionHeader']))
        customer_data = [
            ['Customer:', payment.customer.name],
            ['Phone:', payment.customer.phone],
        ]
        customer_table = Table(customer_data, colWidths=[60, 150])
        customer_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(customer_table)
        # Reduced spacer
        elements.append(Spacer(1, 3*mm))
        
        # Amount Box (Gold Highlighted - Main Focus)
        elements.append(Paragraph("AMOUNT RECEIVED:", self.styles['SectionHeader']))
        
        amount_display = self._format_currency(payment.amount)
        amount_words = self._amount_in_words(payment.amount)
        
        amount_data = [
            [amount_display],
            [f"({amount_words})"],
        ]
        # Slightly narrower width to account for tighter margins
        amount_table = Table(amount_data, colWidths=[doc.width])
        amount_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (0, 0), 22),
            ('FONTNAME', (0, 1), (0, 1), UNICODE_FONT),
            ('FONTSIZE', (0, 1), (0, 1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (0, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 1), (0, 1), colors.gray),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
            ('BOX', (0, 0), (-1, -1), 2, GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(amount_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Payment Details
        elements.append(Paragraph("PAYMENT DETAILS:", self.styles['SectionHeader']))
        details_data = [
            ['Method:', payment.get_method_display()],
            ['Account:', payment.payment_account.bank_name if payment.payment_account else 'Cash'],
            ['Reference:', payment.reference or 'N/A'],
        ]
        details_table = Table(details_data, colWidths=[60, 150])
        details_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(details_table)
        # Reduced spacer
        elements.append(Spacer(1, 2*mm))
        
        # Remark
        if payment.remark:
            elements.append(Spacer(1, 2*mm))
            elements.append(Paragraph(f"<b>Remark:</b> {payment.remark}", self.styles['SmallText']))
        
        # ======================================================================
        # NEW PROFESSIONAL SIGNATURE SECTION
        # ======================================================================
        # Pushes section to bottom of page, but not too far
        elements.append(Spacer(1, 5*mm)) 

        # Auto-fill the recorder's name
        recorded_by_text = "Processed By: " + (payment.recorded_by.get_full_name() or payment.recorded_by.username if payment.recorded_by else 'N/A')

        # Create a structured signature block with formal labels and lines above them
        sig_table_data = [
            ['', '', ''], # Empty space for actual signature/stamp
            [recorded_by_text, '', 'Authorized Signatory & Stamp'] # Formal Labels
        ]
        
        # 3 columns: Left Signature, Middle spacer, Right Signature
        sig_table = Table(sig_table_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.4])
        sig_table.setStyle(TableStyle([
            # Style the labels row
            ('FONTNAME', (0, 1), (-1, 1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('TEXTCOLOR', (0, 1), (-1, 1), NAVY_BLUE),
            
            # Add lines ABOVE the labels for signing
            ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),
            ('LINEABOVE', (2, 1), (2, 1), 1, colors.black),
            
            # Alignment
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),
            ('ALIGN', (2, 1), (2, 1), 'RIGHT'),
            
            # Padding between line and text
            ('TOPPADDING', (0, 1), (-1, 1), 4),
            
            # Ensure enough height in top row for a signature/stamp space
            ('ROWHEIGHT', (0,0), (0,0), 15*mm),
        ]))
        elements.append(sig_table)
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        return self._create_response(buffer, f'Receipt_RCP-{payment.pk:05d}.pdf')
    


class SandSaleReceiptGenerator(PDFGenerator):
    """Generate professional branded Receipt for Sand Sales on A5."""
    
    def generate(self, sale):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A5,
            topMargin=6*mm, bottomMargin=6*mm,
            leftMargin=8*mm, rightMargin=8*mm
        )
        elements = []
        
        # Header - Use Branded Header
        elements.extend(self._get_branded_header(width_override=doc.width))
        
        # Document Title
        title_table = Table(
            [['SAND SALE RECEIPT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 2*mm))
        
        # Receipt Info
        receipt_data = [
            ['Receipt No:', f'SND-{sale.pk:05d}'],
            ['Date:', sale.date.strftime('%d/%m/%Y')],
        ]
        receipt_table = Table(receipt_data, colWidths=[70, 140])
        receipt_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (1, 0), (1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elements.append(receipt_table)
        elements.append(Spacer(1, 2*mm))
        
        # Customer Info (if provided)
        if sale.customer_name:
            elements.append(Paragraph("SOLD TO:", self.styles['SectionHeader']))
            customer_data = [
                ['Customer:', sale.customer_name],
                ['Phone:', sale.customer_phone or 'N/A'],
            ]
            customer_table = Table(customer_data, colWidths=[60, 150])
            customer_table.setStyle(TableStyle([
                *self._get_base_table_style(),
                ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
                ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ]))
            elements.append(customer_table)
            elements.append(Spacer(1, 3*mm))
        
        # Sale Details
        elements.append(Paragraph("SALE DETAILS:", self.styles['SectionHeader']))
        details_data = [
            ['Vehicle Type:', sale.vehicle_type.name],
            ['Quantity:', f'{sale.quantity} vehicle(s)'],
            ['Unit Price:', self._format_currency(sale.unit_price)],
        ]
        details_table = Table(details_data, colWidths=[80, 130])
        details_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 3*mm))
        
        # Amount Box (Gold Highlighted - Main Focus)
        elements.append(Paragraph("TOTAL AMOUNT:", self.styles['SectionHeader']))
        
        amount_display = self._format_currency(sale.total_amount)
        amount_words = self._amount_in_words(sale.total_amount)
        
        amount_data = [
            [amount_display],
            [f"({amount_words})"],
        ]
        amount_table = Table(amount_data, colWidths=[doc.width])
        amount_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (0, 0), 22),
            ('FONTNAME', (0, 1), (0, 1), UNICODE_FONT),
            ('FONTSIZE', (0, 1), (0, 1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (0, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 1), (0, 1), colors.gray),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
            ('BOX', (0, 0), (-1, -1), 2, GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(amount_table)
        elements.append(Spacer(1, 2*mm))
        
        # Payment Details
        elements.append(Paragraph("PAYMENT DETAILS:", self.styles['SectionHeader']))
        payment_data = [
            ['Payment Account:', sale.payment_account.bank_name],
            ['Status:', 'PAID'],
        ]
        payment_table = Table(payment_data, colWidths=[80, 130])
        payment_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(payment_table)
        elements.append(Spacer(1, 2*mm))
        
        # Remark
        if sale.remark:
            elements.append(Spacer(1, 2*mm))
            elements.append(Paragraph(f"<b>Remark:</b> {sale.remark}", self.styles['SmallText']))
        
        # Signature Section
        elements.append(Spacer(1, 5*mm))
        
        recorded_by_text = "Processed By: " + (sale.recorded_by.get_full_name() or sale.recorded_by.username if sale.recorded_by else 'N/A')
        
        sig_table_data = [
            ['', '', ''],
            [recorded_by_text, '', 'Authorized Signatory & Stamp']
        ]
        
        sig_table = Table(sig_table_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.4])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 1), (-1, 1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('TEXTCOLOR', (0, 1), (-1, 1), NAVY_BLUE),
            ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),
            ('LINEABOVE', (2, 1), (2, 1), 1, colors.black),
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),
            ('ALIGN', (2, 1), (2, 1), 'RIGHT'),
            ('TOPPADDING', (0, 1), (-1, 1), 4),
            ('ROWHEIGHT', (0,0), (0,0), 15*mm),
        ]))
        elements.append(sig_table)
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        return self._create_response(buffer, f'SandReceipt_SND-{sale.pk:05d}.pdf')


# ==============================================================================
# CUSTOMER STATEMENT GENERATOR
# ==============================================================================

# ==============================================================================
# CUSTOMER STATEMENT GENERATOR (REVERSE CALCULATION - MATHEMATICALLY SAFE)
# ==============================================================================

class CustomerStatementGenerator(PDFGenerator):
    """Generate professional branded Customer Statement on A4."""

    def generate(self, customer, start_date=None, end_date=None):
        from .models import Payment, SupplyLog, ReturnLog, CashRefund
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=12*mm, bottomMargin=12*mm,
            leftMargin=15*mm, rightMargin=15*mm
        )
        elements = []
        
        # Date range defaults
        end_date = end_date or timezone.now().date()
        start_date = start_date or end_date.replace(day=1)
        
        # Header - Use Branded Header
        elements.extend(self._get_branded_header())
        
        # Document Title
        title_table = Table(
            [['CUSTOMER ACCOUNT STATEMENT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        
        # Period
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}",
            self.styles['CenterAlign']
        ))
        elements.append(Spacer(1, 5*mm))
        
        # Customer Info Box
        customer_data = [
            ['Customer:', customer.name, 'Phone:', customer.phone],
            ['Type:', customer.customer_type or 'N/A', 'Email:', customer.email or 'N/A'],
        ]
        customer_table = Table(customer_data, colWidths=[60, 150, 50, 120])
        customer_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(customer_table)
        elements.append(Spacer(1, 5*mm))
        
        # ======================================================================
        # 1. GATHER TRANSACTIONS FOR THIS PERIOD
        # ======================================================================
        transactions = []
        period_debit = Decimal('0')
        period_credit = Decimal('0')
        
        # Payments (Credit)
        for p in Payment.objects.filter(customer=customer, date__gte=start_date, date__lte=end_date):
            transactions.append({
                'date': p.date,
                'type': 'Payment',
                'description': f'{p.get_method_display()} - {p.reference or "No Ref"}',
                'debit': None,
                'credit': p.amount
            })
            period_credit += p.amount
        
        # Supplies (Debit)
        for s in SupplyLog.objects.filter(customer=customer, date__gte=start_date, date__lte=end_date):
            transactions.append({
                'date': s.date,
                'type': 'Supply',
                'description': f'{s.quantity_delivered} x {s.block_type.name}',
                'debit': s.total_value,
                'credit': None
            })
            period_debit += s.total_value
        
        # Returns (Credit)
        for r in ReturnLog.objects.filter(customer=customer, date__gte=start_date, date__lte=end_date, credit_customer=True):
            transactions.append({
                'date': r.date,
                'type': 'Return',
                'description': f'{r.quantity_returned} x {r.block_type.name} returned',
                'debit': None,
                'credit': r.credit_value
            })
            period_credit += r.credit_value
        
        # Refunds (Debit)
        for rf in CashRefund.objects.filter(customer=customer, date__gte=start_date, date__lte=end_date):
            transactions.append({
                'date': rf.date,
                'type': 'Refund',
                'description': f'Cash refund - {rf.reason[:30]}',
                'debit': rf.amount,
                'credit': None
            })
            period_debit += rf.amount
        
        # Sort by date
        transactions.sort(key=lambda x: x['date'])

        # ======================================================================
        # 2. CALCULATE OPENING BALANCE (REVERSE METHOD)
        # ======================================================================
        # We start with the CURRENT known balance from the DB
        final_balance = customer.account_balance
        
        # We work BACKWARDS to find what the balance was at the start
        # Start Balance = End Balance - (Everything that added to debt) + (Everything that reduced debt)
        opening_balance = final_balance - period_debit + period_credit

        # ======================================================================
        # 3. BUILD TABLE
        # ======================================================================
        
        elements.append(Paragraph("TRANSACTION HISTORY", self.styles['SectionHeader']))
        
        trans_data = [['Date', 'Type', 'Description', 'Debit (₦)', 'Credit (₦)']]
        
        # Add Opening Balance Row
        trans_data.append([
            start_date.strftime('%d/%m/%Y'),
            'B/F',
            'Opening Balance Brought Forward',
            self._format_currency(opening_balance) if opening_balance > 0 else '',
            self._format_currency(abs(opening_balance)) if opening_balance < 0 else ''
        ])
        
        for t in transactions:
            debit_str = self._format_currency(t['debit']) if t['debit'] else ''
            credit_str = self._format_currency(t['credit']) if t['credit'] else ''
            
            desc = t['description']
            if len(desc) > 35:
                desc = desc[:32] + '...'
            
            trans_data.append([
                t['date'].strftime('%d/%m/%Y'),
                t['type'],
                desc,
                debit_str,
                credit_str
            ])
        
        # Totals row (These are just the Period Totals)
        trans_data.append(['', '', 'PERIOD TOTALS:', self._format_currency(period_debit), self._format_currency(period_credit)])
        
        trans_table = Table(trans_data, colWidths=[60, 55, 165, 60, 60])
        
        # Build style
        style_commands = [
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.lightgrey),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, NAVY_BLUE),
            ('FONTNAME', (2, -1), (-1, -1), UNICODE_FONT_BOLD),
        ]
        
        # Alternating row colors
        for i in range(1, len(trans_data) - 1):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))
        
        trans_table.setStyle(TableStyle(style_commands))
        elements.append(trans_table)
        elements.append(Spacer(1, 6*mm))
        
        # Account Summary Box
        elements.append(Paragraph("ACCOUNT SUMMARY", self.styles['SectionHeader']))
        
        summary_data = [
            ['Opening Balance:', self._format_currency(opening_balance)],
            ['Period Debit (Supplies):', self._format_currency(period_debit)],
            ['Period Credit (Payments):', self._format_currency(period_credit)],
            ['', ''],
            ['CURRENT BALANCE:', self._format_currency(final_balance)],
            ['STATUS:', customer.balance_status],
        ]
        summary_table = Table(summary_data, colWidths=[200, 180])
        summary_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 4), (-1, 4), 1.5, GOLD), # Line above Current Balance
            ('FONTSIZE', (0, 4), (-1, 5), 12),
            ('TEXTCOLOR', (0, 4), (-1, 5), NAVY_BLUE),
            ('BACKGROUND', (0, 4), (-1, 5), LIGHT_GOLD),
        ]))
        elements.append(summary_table)
        
        # Generation timestamp
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Statement generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        
        filename = f'Statement_{customer.name.replace(" ", "_")}_{end_date}.pdf'
        return self._create_response(buffer, filename)


class ProformaInvoiceGenerator(PDFGenerator):
    def generate(self, sales_order):
        from .models import PaymentAccount

        # 1. Setup Document with tight margins to maximize space
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=8 * mm, bottomMargin=8 * mm,
            leftMargin=10 * mm, rightMargin=10 * mm
        )
        elements = []

        # --- LOGIC SWITCH: Is this a Final Invoice or still a Proforma? ---
        is_final = sales_order.status == 'COMPLETED'

        # Define Labels based on status
        doc_title = "FINAL INVOICE" if is_final else "PROFORMA INVOICE"
        id_prefix = "INV" if is_final else "PF"
        id_label = "Invoice No:" if is_final else "Proforma No:"
        deliver_label = "DELIVERED TO:" if is_final else "DELIVER TO:"
        date_label_2 = "Due Date:" if is_final else "Valid Until:"

        # =========================================================
        # 1. CUSTOM HEADER
        # =========================================================

        # Get Logo - Bolder (35mm)
        logo = get_logo_with_fallback(self.logo_path, width=35 * mm, height=35 * mm)

        # Style 1: Name & Tagline
        header_title_style = ParagraphStyle(
            'HeaderTitle', parent=self.styles['Normal'],
            fontName=UNICODE_FONT_BOLD, fontSize=11, textColor=NAVY_BLUE, leading=13
        )
        header_sub_style = ParagraphStyle(
            'HeaderSub', parent=self.styles['Normal'],
            fontName=UNICODE_FONT, fontSize=8, textColor=GOLD, leading=10
        )

        # Style 2: Address & Contact
        header_center_style = ParagraphStyle(
            'HeaderCenter', parent=self.styles['Normal'],
            fontName=UNICODE_FONT, fontSize=9, textColor=NAVY_BLUE, leading=12,
            alignment=TA_CENTER
        )

        # Part A: Logo + Company Name/Tagline
        company_details_left = [
            Paragraph(COMPANY_NAME, header_title_style),
            Paragraph(COMPANY_TAGLINE, header_sub_style),
        ]

        header_data = [[logo, company_details_left]]
        header_table = Table(header_data, colWidths=[40 * mm, doc.width - 40 * mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)

        # Part B: Address & Contact
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(COMPANY_ADDRESS, header_center_style))
        elements.append(Paragraph(f"Tel: {COMPANY_PHONE} | Email: {COMPANY_EMAIL}", header_center_style))

        # Gold Line separator
        elements.append(Spacer(1, 2 * mm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceBefore=1, spaceAfter=1))
        elements.append(Spacer(1, 3 * mm))

        # =========================================================
        # 2. DOCUMENT TITLE BAR (DYNAMIC)
        # =========================================================
        title_table = Table(
            [[doc_title]],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 3 * mm))

        # =========================================================
        # 3. INFO BOX (DYNAMIC LABELS)
        # =========================================================
        proforma_data = [
            [
                id_label, f'{id_prefix}-{sales_order.pk:05d}',
                'Date:', sales_order.date.strftime('%d/%m/%Y')
            ],
            [
                date_label_2,
                sales_order.valid_until.strftime('%d/%m/%Y') if sales_order.valid_until else 'Upon Receipt',
                'Status:', sales_order.get_status_display()
            ],
        ]
        # Adjusted widths
        proforma_table = Table(proforma_data, colWidths=[25 * mm, 65 * mm, 20 * mm, 65 * mm])
        proforma_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),  # Labels Bold
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),  # Labels Bold
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('TEXTCOLOR', (2, 0), (2, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(proforma_table)
        elements.append(Spacer(1, 4 * mm))

        # =========================================================
        # 4. BILL TO / DELIVER TO (DYNAMIC HEADER)
        # =========================================================
        bill_to_data = [
            ['BILL TO:'],
            [sales_order.customer.name],
            [sales_order.customer.phone],
            [sales_order.customer.email or ''],
        ]
        bill_to_table = Table(bill_to_data, colWidths=[92 * mm])
        bill_to_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, 0), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, 0), NAVY_BLUE),
            ('FONTSIZE', (0, 1), (0, 1), 10),
            ('FONTNAME', (0, 1), (0, 1), UNICODE_FONT_BOLD),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))

        deliver_to_data = [
            [deliver_label],  # Dynamic Header
            [sales_order.site.name],
            [sales_order.site.address[:45] + '...' if len(sales_order.site.address) > 45 else sales_order.site.address],
            [f"Contact: {sales_order.site.contact_person or 'N/A'} ({sales_order.site.contact_phone or 'N/A'})"],
        ]
        deliver_to_table = Table(deliver_to_data, colWidths=[92 * mm])
        deliver_to_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, 0), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, 0), NAVY_BLUE),
            ('FONTSIZE', (0, 1), (0, 1), 10),
            ('FONTNAME', (0, 1), (0, 1), UNICODE_FONT_BOLD),
            ('BOX', (0, 0), (-1, -1), 1, GOLD),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))

        combined_data = [[bill_to_table, deliver_to_table]]
        combined_table = Table(combined_data, colWidths=[95 * mm, 95 * mm])
        combined_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(combined_table)
        elements.append(Spacer(1, 4 * mm))

        # =========================================================
        # 5. ORDER DETAILS (UPDATED FOR PER-ITEM DISCOUNT + SURCHARGE)
        # =========================================================
        elements.append(Paragraph("ORDER DETAILS:", self.styles['SectionHeader']))

        # Check if there's a surcharge
        has_surcharge = sales_order.surcharge_per_block > 0

        if has_surcharge:
            items_data = [['Item', 'Qty', 'Base Price', 'Discount', 'Surcharge', 'Net Price', 'Amount']]
        else:
            items_data = [['Item', 'Qty', 'Unit Price', 'Discount', 'Net Price', 'Amount']]

        subtotal = Decimal('0')
        total_qty = 0

        for item in sales_order.items.all():
            base_price = item.block_type.selling_price
            discount = item.discount_per_block
            surcharge = sales_order.surcharge_per_block
            net_price = item.agreed_price
            line_total = item.line_total

            if has_surcharge:
                items_data.append([
                    item.block_type.name[:18] + '..' if len(item.block_type.name) > 18 else item.block_type.name,
                    str(item.quantity_requested),
                    self._format_currency(base_price),
                    self._format_currency(discount) if discount > 0 else '-',
                    self._format_currency(surcharge),
                    self._format_currency(net_price),
                    self._format_currency(line_total)
                ])
            else:
                items_data.append([
                    item.block_type.name[:20] + '..' if len(item.block_type.name) > 20 else item.block_type.name,
                    str(item.quantity_requested),
                    self._format_currency(base_price),
                    self._format_currency(discount) if discount > 0 else '-',
                    self._format_currency(net_price),
                    self._format_currency(line_total)
                ])

            subtotal += line_total
            total_qty += item.quantity_requested

        if has_surcharge:
            items_table = Table(items_data, colWidths=[50*mm, 12*mm, 26*mm, 22*mm, 22*mm, 26*mm, 32*mm])
        else:
            items_table = Table(items_data, colWidths=[60*mm, 15*mm, 28*mm, 25*mm, 28*mm, 34*mm])

        style_commands = [
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, 0), 1, NAVY_BLUE),
            ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.lightgrey),
        ]

        for i in range(1, len(items_data)):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))

        items_table.setStyle(TableStyle(style_commands))
        elements.append(items_table)
        elements.append(Spacer(1, 2 * mm))

        # =========================================================
        # 6. TOTALS (UPDATED - REMOVED ORDER-LEVEL DISCOUNT)
        # =========================================================
        summary_data = [
            ['Subtotal:', self._format_currency(subtotal), 'Total Qty:', f'{total_qty} blocks'],
        ]

        # Surcharge note (if applicable)
        surcharge_text = ''
        if sales_order.surcharge_per_block > 0:
            surcharge_text = f"Logistics Surcharge: {self._format_currency(sales_order.surcharge_per_block)}/block (separate)"

        summary_table = Table(summary_data, colWidths=[40 * mm, 50 * mm, 40 * mm, 60 * mm])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(summary_table)

        if surcharge_text:
            elements.append(Paragraph(surcharge_text, self.styles['SmallText']))

        elements.append(Spacer(1, 2 * mm))

        # Total Amount Due
        total_data = [
            ['TOTAL AMOUNT DUE:', self._format_currency(subtotal)],
            ['', f'({self._amount_in_words(subtotal)})'],
        ]
        total_table = Table(total_data, colWidths=[130 * mm, 60 * mm])
        total_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('TEXTCOLOR', (0, 0), (-1, 0), NAVY_BLUE),
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GOLD),
            ('BOX', (0, 0), (-1, 0), 2, GOLD),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (1, 1), (1, 1), 7),
            ('TEXTCOLOR', (1, 1), (1, 1), colors.gray),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, 1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 2),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 4 * mm))

        # =========================================================
        # 7. PAYMENT & TERMS (DYNAMIC)
        # =========================================================
        elements.append(Paragraph("PAYMENT INSTRUCTIONS:", self.styles['SectionHeader']))

        accounts = PaymentAccount.objects.filter(is_active=True, business_unit='BLOCK')
        payment_data = [['Bank', 'Account Name', 'Account Number']]
        for acc in accounts:
            payment_data.append([acc.bank_name, acc.account_name, acc.account_number])

        if len(payment_data) > 1:
            payment_table = Table(payment_data, colWidths=[60 * mm, 70 * mm, 60 * mm])
            payment_table.setStyle(TableStyle([
                *self._get_base_table_style(),
                ('BACKGROUND', (0, 0), (-1, 0), GOLD),
                ('TEXTCOLOR', (0, 0), (-1, 0), NAVY_BLUE),
                ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, NAVY_BLUE),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('BACKGROUND', (0, 1), (-1, -1), LIGHT_GOLD),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(payment_table)
        else:
            elements.append(Paragraph("Please contact us for payment details.", self.styles['NormalText']))

        elements.append(Spacer(1, 4 * mm))

        # Terms and Conditions - DYNAMIC SWITCH
        elements.append(Paragraph("TERMS & CONDITIONS:", self.styles['SectionHeader']))

        if is_final:
            # FINAL INVOICE TERMS
            terms_data = [
                ['1.', 'Goods received in good condition are not returnable.'],
                ['2.', 'Exchange allowed only within 48 hours for verified factory defects.'],
                ['3.', 'Payment confirms acceptance of these terms.'],
                ['4.', 'Title of goods passes to buyer upon full payment.'],
            ]
        else:
            # PROFORMA TERMS (Original)
            validity_days = 14
            if sales_order.valid_until and sales_order.date:
                validity_days = (sales_order.valid_until - sales_order.date).days

            terms_data = [
                ['1.', f'Valid for {validity_days} days. Prices subject to change after validity.'],
                ['2.', 'Delivery begins 3-5 working days after payment confirmation.'],
                ['3.', 'Payment confirms acceptance of terms.'],
                ['4.', 'Goods remain property of Jafan Standard Block Industry until fully paid.'],
            ]

        # Collect discount reasons from items
        discount_reasons = [item.discount_reason for item in sales_order.items.all() if item.discount_reason]
        if discount_reasons:
            reasons_text = "; ".join(discount_reasons)
            terms_data.append(['5.', f'Discount Reason(s): {reasons_text}'])

        terms_table = Table(terms_data, colWidths=[10 * mm, 180 * mm])
        terms_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elements.append(terms_table)

        # Notes
        if sales_order.notes:
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(f"<b>NOTES:</b> {sales_order.notes}", self.styles['NormalText']))

        # Signatures
        elements.append(Spacer(1, 3 * mm))
        sig_data = [['Signed Management']]
        sig_table = Table(sig_data, colWidths=[170])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), NAVY_BLUE),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(sig_table)

        # Footer
        elements.extend(self._get_footer())

        doc.build(elements)
        return self._create_response(buffer, f'{id_prefix}-{sales_order.pk:05d}.pdf')
    

# ==============================================================================
# VENDOR STATEMENT GENERATOR
# ==============================================================================

class VendorStatementGenerator(PDFGenerator):
    """Generate professional branded Vendor Statement on A4."""

    def generate(self, vendor, start_date=None, end_date=None):
        from .models import Expense, ProcurementLog, VendorPayment, SupplyLog, AccountTransfer
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=12*mm, bottomMargin=12*mm,
            leftMargin=15*mm, rightMargin=15*mm
        )
        elements = []
        
        # Date range defaults
        end_date = end_date or timezone.now().date()
        start_date = start_date or end_date.replace(day=1)
        
        # Header
        elements.extend(self._get_branded_header())
        
        # Document Title
        title_table = Table(
            [['VENDOR ACCOUNT STATEMENT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        
        # Period
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}",
            self.styles['CenterAlign']
        ))
        elements.append(Spacer(1, 5*mm))
        
        # Vendor Info Box
        vendor_type = "INTERNAL" if vendor.is_internal else "EXTERNAL"
        vendor_data = [
            ['Vendor:', vendor.name, 'Type:', vendor_type],
            ['Phone:', vendor.phone or 'N/A', 'Supply Type:', getattr(vendor, 'supply_type', 'N/A') or 'N/A'],
        ]
        vendor_table = Table(vendor_data, colWidths=[50, 160, 70, 110])
        vendor_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(vendor_table)
        elements.append(Spacer(1, 5*mm))
        
        # ======================================================================
        # GATHER TRANSACTIONS
        # ======================================================================
        transactions = []
        period_debit = Decimal('0')   # What we owe vendor (increases balance)
        period_credit = Decimal('0')  # What we paid vendor (decreases balance)
        
        # ======================================================================
        # CHECK IF INTERNAL TRANSPORT VENDOR
        # ======================================================================
        is_internal_transport = (
            vendor.is_internal and 
            getattr(vendor, 'supply_type', None) == 'TRANSPORT'
        )
        
        if is_internal_transport:
            # ==================================================================
            # INTERNAL TRANSPORT: Special Logic
            # ==================================================================
            
            # ------------------------------------------------------------------
            # DEBITS: Logistics Income from Block Deliveries
            # ------------------------------------------------------------------
            for s in SupplyLog.objects.filter(
                date__gte=start_date,
                date__lte=end_date,
                delivery_type='DELIVERED',
                logistics_income__gt=0
            ).select_related('customer', 'block_type', 'site'):
                transactions.append({
                    'date': s.date,
                    'type': 'Delivery',
                    'description': f'{s.quantity_delivered} {s.block_type.name} to {s.customer.name}',
                    'debit': s.logistics_income,
                    'credit': None,
                })
                period_debit += s.logistics_income
            
            # ------------------------------------------------------------------
            # DEBITS: Internal Haulage from Procurements
            # ------------------------------------------------------------------
            for p in ProcurementLog.objects.filter(
                date__gte=start_date,
                date__lte=end_date,
                is_internal_haulage=True,
                haulage_fee__gt=0
            ).select_related('material', 'vendor'):
                supplier_name = p.vendor.name if p.vendor else 'Unknown'
                transactions.append({
                    'date': p.date,
                    'type': 'Haulage',
                    'description': f'{p.quantity} {p.material.get_name_display()} from {supplier_name}',
                    'debit': p.haulage_fee,
                    'credit': None,
                })
                period_debit += p.haulage_fee
            
            # ------------------------------------------------------------------
            # CREDITS: Transport Settlements (AccountTransfer)
            # ------------------------------------------------------------------
            for t in AccountTransfer.objects.filter(
                date__gte=start_date,
                date__lte=end_date,
                is_transport_settlement=True
            ).select_related('from_account', 'to_account'):
                ref_text = f" (Ref: {t.reference})" if t.reference else ""
                transactions.append({
                    'date': t.date,
                    'type': 'Settlement',
                    'description': f'Settlement to {t.to_account.bank_name}{ref_text}',
                    'debit': None,
                    'credit': t.amount,
                })
                period_credit += t.amount
            
            # ------------------------------------------------------------------
            # CREDITS: VendorPayment (if any direct payments to Transport)
            # ------------------------------------------------------------------
            for vp in VendorPayment.objects.filter(
                vendor=vendor,
                date__gte=start_date,
                date__lte=end_date
            ):
                ref_text = f" (Ref: {vp.reference})" if vp.reference else ""
                transactions.append({
                    'date': vp.date,
                    'type': 'Payment',
                    'description': f'Payment to Vendor{ref_text}',
                    'debit': None,
                    'credit': vp.amount,
                })
                period_credit += vp.amount
        
        else:
            # ==================================================================
            # REGULAR VENDOR: Standard Logic
            # ==================================================================
            
            # ------------------------------------------------------------------
            # DEBITS: Procurement (Credit purchases only - unpaid)
            # ------------------------------------------------------------------
            for p in ProcurementLog.objects.filter(
                vendor=vendor, 
                date__gte=start_date, 
                date__lte=end_date,
                is_paid=False  # Only CREDIT purchases increase vendor balance
            ).select_related('material'):
                transactions.append({
                    'date': p.date,
                    'type': 'Purchase',
                    'description': f'{p.quantity} {p.material.get_name_display()}',
                    'debit': p.total_cost,
                    'credit': None,
                })
                period_debit += p.total_cost
            
            # ------------------------------------------------------------------
            # DEBITS: Manual Expenses (Credit only - unpaid, not auto-synced)
            # ------------------------------------------------------------------
            for e in Expense.objects.filter(
                vendor=vendor, 
                date__gte=start_date, 
                date__lte=end_date,
                is_auto_synced=False,
                is_paid=False  # Only CREDIT expenses increase vendor balance
            ).select_related('category'):
                desc = e.description[:20] if e.description else ''
                transactions.append({
                    'date': e.date,
                    'type': 'Expense',
                    'description': f'{e.category.name}: {desc}',
                    'debit': e.amount,
                    'credit': None,
                })
                period_debit += e.amount
            
            # ------------------------------------------------------------------
            # CREDITS: VendorPayment (Payments TO vendor)
            # ------------------------------------------------------------------
            for vp in VendorPayment.objects.filter(
                vendor=vendor,
                date__gte=start_date,
                date__lte=end_date
            ):
                ref_text = f" (Ref: {vp.reference})" if vp.reference else ""
                transactions.append({
                    'date': vp.date,
                    'type': 'Payment',
                    'description': f'Payment to Vendor{ref_text}',
                    'debit': None,
                    'credit': vp.amount,
                })
                period_credit += vp.amount
        
        # Sort by date
        transactions.sort(key=lambda x: x['date'])
        
        # ======================================================================
        # CALCULATE OPENING BALANCE
        # Opening = Closing - Period Debits + Period Credits
        # ======================================================================
        final_balance = vendor.account_balance
        opening_balance = final_balance - period_debit + period_credit
        
        # ======================================================================
        # BUILD TABLE
        # ======================================================================
        elements.append(Paragraph("TRANSACTION HISTORY", self.styles['SectionHeader']))
        
        trans_data = [['Date', 'Type', 'Description', 'Debit (₦)', 'Credit (₦)', 'Balance']]
        
        # Opening Balance Row
        running_balance = opening_balance
        trans_data.append([
            start_date.strftime('%d/%m/%Y'),
            'B/F',
            'Opening Balance',
            '',
            '',
            self._format_currency(running_balance)
        ])
        
        for t in transactions:
            # Update running balance
            if t['debit']:
                running_balance += t['debit']
            if t['credit']:
                running_balance -= t['credit']
            
            debit_str = self._format_currency(t['debit']) if t['debit'] else ''
            credit_str = self._format_currency(t['credit']) if t['credit'] else ''
            
            desc = t['description']
            if len(desc) > 30:
                desc = desc[:27] + '...'
            
            trans_data.append([
                t['date'].strftime('%d/%m/%Y'),
                t['type'],
                desc,
                debit_str,
                credit_str,
                self._format_currency(running_balance)
            ])
        
        # Totals row
        trans_data.append([
            '', '', 'PERIOD TOTALS:', 
            self._format_currency(period_debit), 
            self._format_currency(period_credit), 
            ''
        ])
        
        trans_table = Table(trans_data, colWidths=[50, 50, 140, 65, 65, 65])
        
        style_commands = [
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.lightgrey),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, NAVY_BLUE),
            ('FONTNAME', (2, -1), (-1, -1), UNICODE_FONT_BOLD),
        ]
        
        # Alternating row colors
        for i in range(1, len(trans_data) - 1):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))
        
        trans_table.setStyle(TableStyle(style_commands))
        elements.append(trans_table)
        elements.append(Spacer(1, 6*mm))
        
        # Account Summary Box
        elements.append(Paragraph("ACCOUNT SUMMARY", self.styles['SectionHeader']))
        
        if final_balance > 0:
            balance_status = "We Owe Vendor"
            balance_color = "#dc3545"  # Red
        elif final_balance < 0:
            balance_status = "Vendor Owes Us"
            balance_color = "#007bff"  # Blue
        else:
            balance_status = "Settled"
            balance_color = "#28a745"  # Green
        
        # Customize labels for internal transport
        if is_internal_transport:
            debit_label = "Period Services (Block Owes Transport):"
            credit_label = "Period Settlements (Paid to Transport):"
        else:
            debit_label = "Period Purchases (Debit):"
            credit_label = "Period Payments (Credit):"
        
        summary_data = [
            ['Opening Balance:', self._format_currency(opening_balance)],
            [debit_label, self._format_currency(period_debit)],
            [credit_label, self._format_currency(period_credit)],
            ['', ''],
            ['CLOSING BALANCE:', self._format_currency(final_balance)],
            ['STATUS:', balance_status],
        ]
        summary_table = Table(summary_data, colWidths=[200, 180])
        summary_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 4), (-1, 4), 1.5, GOLD),
            ('FONTSIZE', (0, 4), (-1, 5), 12),
            ('TEXTCOLOR', (0, 4), (-1, 5), NAVY_BLUE),
            ('BACKGROUND', (0, 4), (-1, 5), LIGHT_GOLD),
        ]))
        elements.append(summary_table)
        
        # Generation timestamp
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Statement generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        
        filename = f'VendorStatement_{vendor.name.replace(" ", "_")}_{end_date}.pdf'
        return self._create_response(buffer, filename)
    

# ==============================================================================
# ACCOUNT STATEMENT GENERATOR
# ==============================================================================

class AccountStatementGenerator(PDFGenerator):
    """Generate professional branded Account Statement on A4 (like a bank statement)."""

    def generate(self, account, start_date=None, end_date=None):
        from .models import Payment, Expense, ProcurementLog, CashRefund, BankCharge, AccountTransfer, VendorPayment, SandSale, Loan, LoanRepayment, TeamPayment, FuelLog, MaintenanceLog, TransportRevenue, QuickSale
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=12*mm, bottomMargin=12*mm,
            leftMargin=15*mm, rightMargin=15*mm
        )
        elements = []
        
        # Date range defaults
        end_date = end_date or timezone.now().date()
        start_date = start_date or end_date.replace(day=1)
        
        # Header
        elements.extend(self._get_branded_header())
        
        # Document Title
        title_table = Table(
            [['ACCOUNT STATEMENT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        
        # Period
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}",
            self.styles['CenterAlign']
        ))
        elements.append(Spacer(1, 5*mm))
        
        # Account Info Box
        account_data = [
            ['Account:', account.bank_name, 'Type:', account.get_account_type_display()],
            ['Account No:', account.account_number or 'N/A', 'Business Unit:', account.get_business_unit_display()],
            ['Account Name:', account.account_name, '', ''],
        ]
        account_table = Table(account_data, colWidths=[80, 150, 75, 110])
        account_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(account_table)
        elements.append(Spacer(1, 5*mm))
        
        # ======================================================================
        # GATHER TRANSACTIONS
        # ======================================================================
        transactions = []
        period_debit = Decimal('0')   # Money going OUT
        period_credit = Decimal('0')  # Money coming IN
        
        # ----------------------------------------------------------------------
        # CREDITS: Payments received from customers (money IN)
        # ----------------------------------------------------------------------
        for p in Payment.objects.filter(
            payment_account=account, 
            date__gte=start_date, 
            date__lte=end_date
        ):
            transactions.append({
                'date': p.date,
                'description': f'Payment: {p.customer.name}',
                'reference': p.reference or '',
                'debit': None,
                'credit': p.amount
            })
            period_credit += p.amount
        

        # ----------------------------------------------------------------------
        # CREDITS: Sand Sales (money IN)
        # ----------------------------------------------------------------------
        for ss in SandSale.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            desc = f'Sand Sale: {ss.quantity}x {ss.vehicle_type.name}'
            if ss.customer_name:
                desc += f' ({ss.customer_name})'
            transactions.append({
                'date': ss.date,
                'description': desc,
                'reference': f'SND-{ss.pk:05d}',
                'debit': None,
                'credit': ss.total_amount
            })
            period_credit += ss.total_amount
            


        # ----------------------------------------------------------------------
        # CREDITS: Quick Sales (money IN)
        # ----------------------------------------------------------------------
        for qs in QuickSale.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            transactions.append({
                'date': qs.date,
                'description': f'Quick Sale: {qs.quantity}x {qs.block_type.name}',
                'reference': f'QS-{qs.pk:05d}',
                'debit': None,
                'credit': qs.total_amount
            })
            period_credit += qs.total_amount





        # ----------------------------------------------------------------------
        # DEBITS: Expenses paid (money OUT)
        # ----------------------------------------------------------------------
        for e in Expense.objects.filter(
            payment_account=account, 
            date__gte=start_date, 
            date__lte=end_date, 
            is_paid=True
        ):
            transactions.append({
                'date': e.payment_date or e.date,
                'description': f'Expense: {e.category.name}',
                'reference': e.receipt_number or '',
                'debit': e.amount,
                'credit': None
            })
            period_debit += e.amount
        
        # ----------------------------------------------------------------------
        # DEBITS: Vendor Payments (money OUT) - NEW!
        # ----------------------------------------------------------------------
        for vp in VendorPayment.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            transactions.append({
                'date': vp.date,
                'description': f'Vendor Payment: {vp.vendor.name}',
                'reference': vp.reference or '',
                'debit': vp.amount,
                'credit': None
            })
            period_debit += vp.amount
        
        # ----------------------------------------------------------------------
        # DEBITS: Cash Refunds to customers (money OUT)
        # ----------------------------------------------------------------------
        for r in CashRefund.objects.filter(
            payment_account=account, 
            date__gte=start_date, 
            date__lte=end_date
        ):
            transactions.append({
                'date': r.date,
                'description': f'Refund: {r.customer.name}',
                'reference': '',
                'debit': r.amount,
                'credit': None
            })
            period_debit += r.amount
        
        # ----------------------------------------------------------------------
        # DEBITS: Bank Charges (money OUT)
        # ----------------------------------------------------------------------
        for b in BankCharge.objects.filter(
            account=account, 
            date__gte=start_date, 
            date__lte=end_date
        ):
            transactions.append({
                'date': b.date,
                'description': f'Bank Charge: {b.charge_type}',
                'reference': b.reference or '',
                'debit': b.amount,
                'credit': None
            })
            period_debit += b.amount
        
        # ----------------------------------------------------------------------
        # DEBITS: Transfers OUT (money OUT)
        # ----------------------------------------------------------------------
        for t in AccountTransfer.objects.filter(
            from_account=account, 
            date__gte=start_date, 
            date__lte=end_date
        ):
            desc = f'Transfer to: {t.to_account.bank_name}'
            if t.is_transport_settlement:
                desc = f'Settlement to: {t.to_account.bank_name}'
            transactions.append({
                'date': t.date,
                'description': desc,
                'reference': t.reference or '',
                'debit': t.amount,
                'credit': None
            })
            period_debit += t.amount


        # ----------------------------------------------------------------------
        # DEBITS: Loans Given (money OUT)
        # ----------------------------------------------------------------------
        for loan in Loan.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            transactions.append({
                'date': loan.date,
                'description': f'Loan: {loan.debtor.name}',
                'reference': f'LOAN-{loan.pk:05d}',
                'debit': loan.amount,
                'credit': None
            })
            period_debit += loan.amount

        # ----------------------------------------------------------------------
        # CREDITS: Loan Repayments (money IN)
        # ----------------------------------------------------------------------
        for repayment in LoanRepayment.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            transactions.append({
                'date': repayment.date,
                'description': f'Loan Repayment: {repayment.loan.debtor.name}',
                'reference': repayment.reference or f'LOAN-{repayment.loan.pk:05d}',
                'debit': None,
                'credit': repayment.amount
            })
            period_credit += repayment.amount
        
        # ----------------------------------------------------------------------
        # CREDITS: Transfers IN (money IN)
        # ----------------------------------------------------------------------
        for t in AccountTransfer.objects.filter(
            to_account=account, 
            date__gte=start_date, 
            date__lte=end_date
        ):
            desc = f'Transfer from: {t.from_account.bank_name}'
            if t.is_transport_settlement:
                desc = f'Settlement from: {t.from_account.bank_name}'
            transactions.append({
                'date': t.date,
                'description': desc,
                'reference': t.reference or '',
                'debit': None,
                'credit': t.amount
            })
            period_credit += t.amount


            # ----------------------------------------------------------------------
        # DEBITS: Paid Procurements (money OUT)
        # ----------------------------------------------------------------------
        for p in ProcurementLog.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date,
            is_paid=True
        ):
            transactions.append({
                'date': p.date,
                'description': f'Procurement: {p.material.get_name_display()}',
                'reference': f'PROC-{p.pk:05d}',
                'debit': p.total_cost,
                'credit': None
            })
            period_debit += p.total_cost

        # ----------------------------------------------------------------------
        # DEBITS: Team Payments (money OUT)
        # ----------------------------------------------------------------------
        for tp in TeamPayment.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            if tp.team:
                desc = f'Team Payment: {tp.team.name}'
            elif tp.employee:
                desc = f'Team Payment: {tp.employee.name}'
            else:
                desc = f'Team Payment: {tp.get_payment_type_display()}'
            transactions.append({
                'date': tp.date,
                'description': desc,
                'reference': tp.reference or '',
                'debit': tp.amount_paid,
                'credit': None
            })
            period_debit += tp.amount_paid

        # ----------------------------------------------------------------------
        # DEBITS: Fuel Logs (money OUT)
        # ----------------------------------------------------------------------
        # ----------------------------------------------------------------------
        # DEBITS: Fuel Logs (money OUT) - Only if payment_account exists
        # ----------------------------------------------------------------------
        # Note: FuelLog may not have payment_account field, skip if not available
        if hasattr(FuelLog, 'payment_account'):
            for fl in FuelLog.objects.filter(
                payment_account=account,
                date__gte=start_date,
                date__lte=end_date
            ):
                transactions.append({
                    'date': fl.date,
                    'description': f'Fuel: {fl.truck.plate_number if fl.truck else "N/A"}',
                    'reference': f'FUEL-{fl.pk:05d}',
                    'debit': fl.total_cost,
                    'credit': None
                })
                period_debit += fl.total_cost

        # ----------------------------------------------------------------------
        # DEBITS: Maintenance Logs (money OUT)
        # ----------------------------------------------------------------------
        for ml in MaintenanceLog.objects.filter(
            payment_account=account,
            date__gte=start_date,
            date__lte=end_date
        ):
            transactions.append({
                'date': ml.date,
                'description': f'Maintenance: {ml.truck.plate_number if ml.truck else "N/A"}',
                'reference': f'MAINT-{ml.pk:05d}',
                'debit': ml.cost,
                'credit': None
            })
            period_debit += ml.cost

        # ----------------------------------------------------------------------
        # CREDITS: Transport Revenue (money IN) - Only if payment_account exists
        # ----------------------------------------------------------------------
        if hasattr(TransportRevenue, 'payment_account'):
            for tr in TransportRevenue.objects.filter(
                payment_account=account,
                date__gte=start_date,
                date__lte=end_date
            ):
                transactions.append({
                    'date': tr.date,
                    'description': f'Transport: {tr.customer_name or "External Job"}',
                    'reference': f'TRV-{tr.pk:05d}',
                    'debit': None,
                    'credit': tr.amount
                })
                period_credit += tr.amount
        
        # Sort ALL transactions by date
        transactions.sort(key=lambda x: x['date'])
        # ======================================================================
        # CALCULATE OPENING BALANCE
        # Opening = Closing - Credits + Debits
        # ======================================================================
        final_balance = account.current_balance
        opening_balance = final_balance - period_credit + period_debit
        
        # ======================================================================
        # BUILD TABLE
        # ======================================================================
        elements.append(Paragraph("TRANSACTION HISTORY", self.styles['SectionHeader']))
        
        trans_data = [['Date', 'Description', 'Reference', 'Debit (₦)', 'Credit (₦)', 'Balance']]
        
        # Opening Balance Row
        running_balance = opening_balance
        trans_data.append([
            start_date.strftime('%d/%m/%Y'),
            'Opening Balance',
            '',
            '',
            '',
            self._format_currency(running_balance)
        ])
        
        for t in transactions:
            # Calculate running balance
            if t['credit']:
                running_balance += t['credit']
            if t['debit']:
                running_balance -= t['debit']
            
            debit_str = self._format_currency(t['debit']) if t['debit'] else ''
            credit_str = self._format_currency(t['credit']) if t['credit'] else ''
            
            desc = t['description']
            if len(desc) > 35:
                desc = desc[:32] + '...'
            
            ref = t['reference']
            if len(ref) > 15:
                ref = ref[:12] + '...'
            
            trans_data.append([
                t['date'].strftime('%d/%m/%Y'),
                desc,
                ref,
                debit_str,
                credit_str,
                self._format_currency(running_balance)
            ])
        
        # Totals row
        trans_data.append([
            '', 'PERIOD TOTALS:', '', 
            self._format_currency(period_debit), 
            self._format_currency(period_credit), 
            ''
        ])
        
        trans_table = Table(trans_data, colWidths=[50, 150, 55, 65, 65, 65])
        
        style_commands = [
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.lightgrey),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, NAVY_BLUE),
            ('FONTNAME', (1, -1), (-1, -1), UNICODE_FONT_BOLD),
        ]
        
        # Alternating row colors
        for i in range(1, len(trans_data) - 1):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))
        
        trans_table.setStyle(TableStyle(style_commands))
        elements.append(trans_table)
        elements.append(Spacer(1, 6*mm))
        
        # Account Summary Box
        elements.append(Paragraph("ACCOUNT SUMMARY", self.styles['SectionHeader']))
        
        summary_data = [
            ['Opening Balance:', self._format_currency(opening_balance)],
            ['Total Credits (Money In):', self._format_currency(period_credit)],
            ['Total Debits (Money Out):', self._format_currency(period_debit)],
            ['', ''],
            ['CLOSING BALANCE:', self._format_currency(final_balance)],
        ]
        summary_table = Table(summary_data, colWidths=[200, 180])
        summary_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 4), (-1, 4), 1.5, GOLD),
            ('FONTSIZE', (0, 4), (-1, 4), 12),
            ('TEXTCOLOR', (0, 4), (-1, 4), NAVY_BLUE),
            ('BACKGROUND', (0, 4), (-1, 4), LIGHT_GOLD),
        ]))
        elements.append(summary_table)
        
        # Last Audit Info (if available)
        if account.last_audit_date:
            elements.append(Spacer(1, 4*mm))
            audit_data = [
                ['Last Audit Date:', account.last_audit_date.strftime('%d/%m/%Y')],
                ['Last Audit Balance:', self._format_currency(account.last_audit_balance or 0)],
            ]
            if account.last_audit_notes:
                audit_data.append(['Audit Notes:', account.last_audit_notes[:50]])
            
            audit_table = Table(audit_data, colWidths=[120, 260])
            audit_table.setStyle(TableStyle([
                *self._get_base_table_style(),
                ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, -1), CREAM),
                ('BOX', (0, 0), (-1, -1), 1, GOLD),
            ]))
            elements.append(audit_table)
        
        # Generation timestamp
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Statement generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        
        filename = f'AccountStatement_{account.bank_name.replace(" ", "_")}_{end_date}.pdf'
        return self._create_response(buffer, filename)
    

# ==============================================================================
# PROFIT & LOSS PDF GENERATOR
# ==============================================================================

class ProfitLossGenerator(PDFGenerator):
    """Generate professional Profit & Loss Statement PDF."""

    def generate(self, start_date, end_date):
        from .services import BlockIndustryPLService
        
        # Get P&L data
        pl_service = BlockIndustryPLService(start_date, end_date, business_unit='BLOCK')
        pl_data = pl_service.get_full_pl()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=15*mm, bottomMargin=15*mm,
            leftMargin=20*mm, rightMargin=20*mm
        )
        elements = []
        
        # Header
        elements.extend(self._get_branded_header())
        
        # Document Title
        title_table = Table(
            [['PROFIT & LOSS STATEMENT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(title_table)
        
        # Period
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Period: {start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}",
            self.styles['CenterAlign']
        ))
        elements.append(Spacer(1, 8*mm))
        
        # ======================================================================
        # P&L TABLE
        # ======================================================================
        pl_table_data = []
        col_widths = [380, 100]
        
        # REVENUE SECTION
        pl_table_data.append(['REVENUE', ''])
        
        for item in pl_data['revenue']['by_block_type']:
            qty = item['quantity'] or 0
            rev = item['revenue'] or Decimal('0')
            pl_table_data.append([
                f"    {item['block_type__name']} ({qty:,} blocks)",
                self._format_currency(rev)
            ])
        
        pl_table_data.append(['Total Block Sales', self._format_currency(pl_data['revenue']['block_sales'])])
        pl_table_data.append([
            f"    Logistics Income (to Transport)",
            f"({self._format_currency(pl_data['revenue']['logistics_income'])})"
        ])
        pl_table_data.append(['TOTAL REVENUE', self._format_currency(pl_data['revenue']['total'])])
        pl_table_data.append(['', ''])  # Spacer row
        
        # COGS SECTION
        pl_table_data.append(['COST OF GOODS SOLD', ''])
        
        for item in pl_data['cogs']['by_block_type']:
            qty = item['quantity'] or 0
            cogs = item['cogs'] or Decimal('0')
            pl_table_data.append([
                f"    {item['block_type__name']} ({qty:,} blocks)",
                self._format_currency(cogs)
            ])
        
        pl_table_data.append(['TOTAL COGS', self._format_currency(pl_data['cogs']['total'])])
        pl_table_data.append(['', ''])  # Spacer row
        
        # GROSS PROFIT
        pl_table_data.append([
            f"GROSS PROFIT ({pl_data['gross_margin_percent']}% margin)",
            self._format_currency(pl_data['gross_profit'])
        ])
        pl_table_data.append(['', ''])  # Spacer row
        
        # OPERATING EXPENSES
        pl_table_data.append(['OPERATING EXPENSES', ''])
        
        for cat, amount in pl_data['operating_expenses']['breakdown'].items():
            pl_table_data.append([f"    {cat}", self._format_currency(amount)])
        
        if not pl_data['operating_expenses']['breakdown']:
            pl_table_data.append(['    (No operating expenses)', ''])
        
        pl_table_data.append(['TOTAL OPERATING EXPENSES', self._format_currency(pl_data['operating_expenses']['total'])])
        pl_table_data.append(['', ''])  # Spacer row
        
        # NET PROFIT
        pl_table_data.append([
            f"NET PROFIT BEFORE TAX ({pl_data['net_margin_percent']}% margin)",
            self._format_currency(pl_data['net_profit'])
        ])
        
        # Build table
        pl_table = Table(pl_table_data, colWidths=col_widths)
        
        # Style the table
        style_commands = [
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]
        
        # Find and style section headers and totals
        for i, row in enumerate(pl_table_data):
            if row[0] in ['REVENUE', 'COST OF GOODS SOLD', 'OPERATING EXPENSES']:
                style_commands.extend([
                    ('BACKGROUND', (0, i), (-1, i), LIGHT_NAVY),
                    ('FONTNAME', (0, i), (-1, i), UNICODE_FONT_BOLD),
                    ('TEXTCOLOR', (0, i), (-1, i), NAVY_BLUE),
                ])
            elif row[0].startswith('TOTAL') or row[0].startswith('NET PROFIT'):
                style_commands.extend([
                    ('FONTNAME', (0, i), (-1, i), UNICODE_FONT_BOLD),
                    ('LINEABOVE', (0, i), (-1, i), 1, NAVY_BLUE),
                ])
            elif row[0].startswith('GROSS PROFIT'):
                style_commands.extend([
                    ('BACKGROUND', (0, i), (-1, i), LIGHT_GOLD),
                    ('FONTNAME', (0, i), (-1, i), UNICODE_FONT_BOLD),
                    ('TEXTCOLOR', (0, i), (-1, i), NAVY_BLUE),
                ])
        
        # Style NET PROFIT row specially
        last_row = len(pl_table_data) - 1
        style_commands.extend([
            ('BACKGROUND', (0, last_row), (-1, last_row), NAVY_BLUE),
            ('TEXTCOLOR', (0, last_row), (-1, last_row), colors.white),
            ('FONTNAME', (0, last_row), (-1, last_row), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, last_row), (-1, last_row), 12),
        ])
        
        pl_table.setStyle(TableStyle(style_commands))
        elements.append(pl_table)
        
        # ======================================================================
        # SUMMARY BOX
        # ======================================================================
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph("FINANCIAL SUMMARY", self.styles['SectionHeader']))
        
        summary_data = [
            ['Total Revenue:', self._format_currency(pl_data['revenue']['total'])],
            ['Cost of Goods Sold:', self._format_currency(pl_data['cogs']['total'])],
            ['Gross Profit:', self._format_currency(pl_data['gross_profit'])],
            ['Gross Margin:', f"{pl_data['gross_margin_percent']}%"],
            ['Operating Expenses:', self._format_currency(pl_data['operating_expenses']['total'])],
            ['', ''],
            ['NET PROFIT:', self._format_currency(pl_data['net_profit'])],
            ['Net Margin:', f"{pl_data['net_margin_percent']}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[250, 150])
        summary_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 6), (-1, 6), 1.5, GOLD),
            ('FONTSIZE', (0, 6), (-1, 6), 12),
            ('BACKGROUND', (0, 6), (-1, 7), LIGHT_GOLD),
            ('TEXTCOLOR', (0, 6), (-1, 7), NAVY_BLUE),
        ]))
        elements.append(summary_table)
        
        # Generation timestamp
        elements.append(Spacer(1, 8*mm))
        elements.append(Paragraph(
            f"Report generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        
        filename = f'ProfitLoss_{start_date}_{end_date}.pdf'
        return self._create_response(buffer, filename)


# ==============================================================================
# CASH FLOW PDF GENERATOR
# ==============================================================================

class CashFlowPDFGenerator(PDFGenerator):
    """Generate professional Cash Flow Statement PDF."""

    def generate(self, start_date, end_date, account=None, business_unit=None):
        from .services import CashFlowService
        
        # Get Cash Flow data
        cf_service = CashFlowService(start_date, end_date, account=account, business_unit=business_unit)
        cf_data = cf_service.get_cash_flow_statement()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=12*mm, bottomMargin=12*mm,
            leftMargin=12*mm, rightMargin=12*mm
        )
        elements = []
        
        # Header
        elements.extend(self._get_branded_header())
        
        # Document Title
        title_table = Table(
            [['CASH FLOW STATEMENT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        
        # Period and Account Info
        elements.append(Spacer(1, 3*mm))
        period_text = f"Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}"
        if account:
            period_text += f"  |  Account: {account.bank_name}"
        if business_unit:
            period_text += f"  |  Unit: {business_unit}"
        elements.append(Paragraph(period_text, self.styles['CenterAlign']))
        elements.append(Spacer(1, 5*mm))
        
        # ======================================================================
        # SUMMARY BOX
        # ======================================================================
        summary_data = [
            ['Opening Balance:', self._format_currency(cf_data['opening_balance']), 
             'Total Inflow:', self._format_currency(cf_data['total_inflow'])],
            ['Closing Balance:', self._format_currency(cf_data['closing_balance']), 
             'Total Outflow:', self._format_currency(cf_data['total_outflow'])],
            ['', '', 'Net Cash Flow:', self._format_currency(cf_data['net_cash_flow'])],
        ]
        summary_table = Table(summary_data, colWidths=[90, 100, 90, 100])
        summary_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 5*mm))
        
        # ======================================================================
        # CATEGORY BREAKDOWN
        # ======================================================================
        elements.append(Paragraph("SUMMARY BY CATEGORY", self.styles['SectionHeader']))
        
        # Inflows
        inflow_data = [['INFLOWS', '']]
        for cat, amount in cf_data['inflow_by_category'].items():
            inflow_data.append([f"  {cat}", self._format_currency(amount)])
        inflow_data.append(['Total Inflows', self._format_currency(cf_data['total_inflow'])])
        
        # Outflows
        outflow_data = [['OUTFLOWS', '']]
        for cat, amount in cf_data['outflow_by_category'].items():
            outflow_data.append([f"  {cat}", self._format_currency(amount)])
        outflow_data.append(['Total Outflows', self._format_currency(cf_data['total_outflow'])])
        
        # Combine side by side
        cat_col_widths = [130, 80]
        
        inflow_table = Table(inflow_data, colWidths=cat_col_widths)
        inflow_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT),           # All cells use Unicode font
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),       # Header bold
            ('FONTNAME', (0, -1), (-1, -1), UNICODE_FONT_BOLD),     # Total row bold
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_NAVY),
            ('LINEABOVE', (0, -1), (-1, -1), 1, NAVY_BLUE),
            ('TEXTCOLOR', (1, 1), (1, -2), colors.green),
        ]))
        
        outflow_table = Table(outflow_data, colWidths=cat_col_widths)
        outflow_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT),           # All cells use Unicode font
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),       # Header bold
            ('FONTNAME', (0, -1), (-1, -1), UNICODE_FONT_BOLD),     # Total row bold
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_NAVY),
            ('LINEABOVE', (0, -1), (-1, -1), 1, NAVY_BLUE),
            ('TEXTCOLOR', (1, 1), (1, -2), colors.red),
        ]))
        
        combined_table = Table([[inflow_table, outflow_table]], colWidths=[220, 220])
        combined_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(combined_table)
        elements.append(Spacer(1, 5*mm))
        
        # ======================================================================
        # TRANSACTION DETAILS
        # ======================================================================
        elements.append(Paragraph("TRANSACTION DETAILS", self.styles['SectionHeader']))
        
        trans_data = [['Date', 'Type', 'Description', 'Inflow', 'Outflow', 'Account']]
        
        # Opening Balance Row
        trans_data.append([
            start_date.strftime('%d/%m/%Y'),
            'B/F',
            'Opening Balance',
            '',
            '',
            self._format_currency(cf_data['opening_balance'])
        ])
        
        for t in cf_data['transactions']:
            inflow_str = self._format_currency(t['inflow']) if t['inflow'] else ''
            outflow_str = self._format_currency(t['outflow']) if t['outflow'] else ''
            
            desc = t['description']
            if len(desc) > 30:
                desc = desc[:27] + '...'
            
            trans_data.append([
                t['date'].strftime('%d/%m/%Y'),
                t['type'][:10],
                desc,
                inflow_str,
                outflow_str,
                t['account'][:12] if t['account'] else ''
            ])
        
        # Totals Row
        trans_data.append([
            '', '', 'TOTALS',
            self._format_currency(cf_data['total_inflow']),
            self._format_currency(cf_data['total_outflow']),
            ''
        ])
        
        # Closing Balance Row
        trans_data.append([
            end_date.strftime('%d/%m/%Y'),
            'C/F',
            'Closing Balance',
            '',
            '',
            self._format_currency(cf_data['closing_balance'])
        ])
        
        trans_table = Table(trans_data, colWidths=[50, 50, 120, 60, 60, 60])
        
        style_commands = [
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('ALIGN', (3, 0), (5, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            # Opening balance row
            ('BACKGROUND', (0, 1), (-1, 1), LIGHT_GOLD),
            # Totals row
            ('LINEABOVE', (0, -2), (-1, -2), 1.5, NAVY_BLUE),
            ('FONTNAME', (2, -2), (-1, -2), UNICODE_FONT_BOLD),
            ('BACKGROUND', (0, -2), (-1, -2), CREAM),
            # Closing balance row
            ('BACKGROUND', (0, -1), (-1, -1), LIGHT_GOLD),
            ('FONTNAME', (0, -1), (-1, -1), UNICODE_FONT_BOLD),
        ]
        
        # Color inflows green, outflows red
        for i in range(2, len(trans_data) - 2):
            if cf_data['transactions'][i-2]['inflow']:
                style_commands.append(('TEXTCOLOR', (3, i), (3, i), colors.green))
            if cf_data['transactions'][i-2]['outflow']:
                style_commands.append(('TEXTCOLOR', (4, i), (4, i), colors.red))
        
        # Alternating row colors
        for i in range(2, len(trans_data) - 2):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))
        
        trans_table.setStyle(TableStyle(style_commands))
        elements.append(trans_table)
        
        # Generation timestamp
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Statement generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        
        account_name = account.bank_name.replace(' ', '_') if account else 'All'
        filename = f'CashFlow_{account_name}_{start_date}_{end_date}.pdf'
        return self._create_response(buffer, filename)
    



class LoanStatementGenerator(PDFGenerator):
    """Generate Loan Statement PDF for a single loan."""

    def generate(self, loan):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=10*mm, bottomMargin=10*mm,
            leftMargin=12*mm, rightMargin=12*mm
        )
        elements = []

        # Header
        elements.extend(self._get_branded_header())

        # Document Title
        title_table = Table(
            [['LOAN STATEMENT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 4*mm))

        # Loan Info Box
        loan_data = [
            ['Loan ID:', f'LOAN-{loan.pk:05d}', 'Date Issued:', loan.date.strftime('%d/%m/%Y')],
            ['Debtor:', loan.debtor.name, 'Phone:', loan.debtor.phone or 'N/A'],
            ['Purpose:', loan.purpose or 'N/A', 'Repayment Mode:', loan.get_repayment_mode_display()],
        ]
        loan_table = Table(loan_data, colWidths=[70, 140, 80, 120])
        loan_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('TEXTCOLOR', (2, 0), (2, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(loan_table)
        elements.append(Spacer(1, 4*mm))

        # Amount Summary Box
        summary_data = [
            ['Loan Amount:', self._format_currency(loan.amount)],
            ['Amount Repaid:', self._format_currency(loan.amount_repaid)],
            ['Outstanding Balance:', self._format_currency(loan.outstanding_balance)],
        ]
        summary_table = Table(summary_data, colWidths=[150, 150])
        summary_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
            ('BOX', (0, 0), (-1, -1), 2, GOLD),
            ('TEXTCOLOR', (0, 2), (-1, 2), NAVY_BLUE),
            ('FONTNAME', (0, 2), (-1, 2), UNICODE_FONT_BOLD),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 5*mm))

        # Transaction History (Loan + Repayments)
        elements.append(Paragraph("TRANSACTION HISTORY", self.styles['SectionHeader']))

        repayments = loan.repayments.all().order_by('date')

        trans_data = [['Date', 'Description', 'Debit', 'Credit', 'Balance']]
        
        # First row: Loan issued
        running_balance = loan.amount
        trans_data.append([
            loan.date.strftime('%d/%m/%Y'),
            f'Loan Issued ({loan.payment_account.bank_name})',
            self._format_currency(loan.amount),
            '-',
            self._format_currency(running_balance)
        ])

        # Repayment rows
        for r in repayments:
            running_balance -= r.amount
            trans_data.append([
                r.date.strftime('%d/%m/%Y'),
                f'Repayment ({r.get_repayment_method_display()})',
                '-',
                self._format_currency(r.amount),
                self._format_currency(running_balance)
            ])

        trans_table = Table(trans_data, colWidths=[60, 150, 75, 75, 75])
        
        style_commands = [
            *self._get_base_table_style(),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            # Loan issued row - highlight
            ('BACKGROUND', (0, 1), (-1, 1), LIGHT_GOLD),
            ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#dc3545')),  # Debit in red
        ]
        
        # Alternating colors for repayments and green for credits
        for i in range(2, len(trans_data)):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))
            style_commands.append(('TEXTCOLOR', (3, i), (3, i), colors.HexColor('#28a745')))  # Credit in green

        trans_table.setStyle(TableStyle(style_commands))
        elements.append(trans_table)

        elements.append(Spacer(1, 5*mm))

        # Status
        status_text = "FULLY REPAID ✓" if loan.is_fully_repaid else f"OUTSTANDING: {self._format_currency(loan.outstanding_balance)}"
        status_color = "#28a745" if loan.is_fully_repaid else "#dc3545"
        
        elements.append(Paragraph(
            f'<b>Status:</b> <font color="{status_color}">{status_text}</font>',
            self.styles['NormalText']
        ))

        # Notes
        if loan.notes:
            elements.append(Spacer(1, 3*mm))
            elements.append(Paragraph(f"<b>Notes:</b> {loan.notes}", self.styles['SmallText']))

        # Generation timestamp
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Statement generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))

        # Footer
        elements.extend(self._get_footer())

        doc.build(elements)
        return self._create_response(buffer, f'LoanStatement_LOAN-{loan.pk:05d}.pdf')
    


class LoanReportGenerator(PDFGenerator):
    """Generate Loan Report PDF for a period."""

    def generate(self, start_date, end_date):
        from .models import Loan
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=10*mm, bottomMargin=10*mm,
            leftMargin=10*mm, rightMargin=10*mm
        )
        elements = []

        # Header
        elements.extend(self._get_branded_header())

        # Document Title
        title_table = Table(
            [['LOAN REPORT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_table)
        
        # Period
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph(
            f"Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}",
            self.styles['CenterAlign']
        ))
        elements.append(Spacer(1, 5*mm))

        # Get loans
        loans = Loan.objects.filter(date__gte=start_date, date__lte=end_date).order_by('date')

        if not loans.exists():
            elements.append(Paragraph("No loans found for this period.", self.styles['NormalText']))
        else:
            # Table
            loan_data = [['Loan ID', 'Date', 'Debtor', 'Amount', 'Repaid', 'Outstanding', 'Status']]
            
            total_amount = Decimal('0')
            total_repaid = Decimal('0')
            total_outstanding = Decimal('0')
            
            for loan in loans:
                status = "✓ Cleared" if loan.is_fully_repaid else "Outstanding"
                loan_data.append([
                    f'LOAN-{loan.pk:05d}',
                    loan.date.strftime('%d/%m/%Y'),
                    loan.debtor.name[:20] + '..' if len(loan.debtor.name) > 20 else loan.debtor.name,
                    self._format_currency(loan.amount),
                    self._format_currency(loan.amount_repaid),
                    self._format_currency(loan.outstanding_balance),
                    status
                ])
                total_amount += loan.amount
                total_repaid += loan.amount_repaid
                total_outstanding += loan.outstanding_balance

            # Totals row
            loan_data.append([
                '', '', 'TOTALS:',
                self._format_currency(total_amount),
                self._format_currency(total_repaid),
                self._format_currency(total_outstanding),
                ''
            ])

            loan_table = Table(loan_data, colWidths=[55, 50, 85, 60, 60, 60, 55])
            
            style_commands = [
                *self._get_base_table_style(),
                ('BACKGROUND', (0, 0), (-1, 0), NAVY_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (3, 0), (5, -1), 'RIGHT'),
                ('ALIGN', (6, 0), (6, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.lightgrey),
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, NAVY_BLUE),
                ('FONTNAME', (2, -1), (-1, -1), UNICODE_FONT_BOLD),
            ]
            
            for i in range(1, len(loan_data) - 1):
                if i % 2 == 0:
                    style_commands.append(('BACKGROUND', (0, i), (-1, i), CREAM))

            loan_table.setStyle(TableStyle(style_commands))
            elements.append(loan_table)

            # Summary
            elements.append(Spacer(1, 5*mm))
            summary_data = [
                ['Total Loans Issued:', f'{loans.count()}', 'Total Amount:', self._format_currency(total_amount)],
                ['Fully Repaid:', f'{loans.filter(is_fully_repaid=True).count()}', 'Total Repaid:', self._format_currency(total_repaid)],
                ['Outstanding:', f'{loans.filter(is_fully_repaid=False).count()}', 'Total Outstanding:', self._format_currency(total_outstanding)],
            ]
            summary_table = Table(summary_data, colWidths=[90, 40, 90, 100])
            summary_table.setStyle(TableStyle([
                *self._get_base_table_style(),
                ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
                ('FONTNAME', (2, 0), (2, -1), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
                ('BOX', (0, 0), (-1, -1), 1, GOLD),
            ]))
            elements.append(summary_table)

        # Generation timestamp
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Report generated on {timezone.now().strftime('%d/%m/%Y at %H:%M')}",
            self.styles['SmallText']
        ))

        # Footer
        elements.extend(self._get_footer())

        doc.build(elements)
        return self._create_response(buffer, f'LoanReport_{start_date}_{end_date}.pdf')
    



class QuickSaleReceiptGenerator(PDFGenerator):
    """Generate professional branded Receipt for Quick Sales on A5."""
    
    def generate(self, sale):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A5,
            topMargin=3*mm, bottomMargin=3*mm,
            leftMargin=8*mm, rightMargin=8*mm
        )
        elements = []
        
        # Header
        elements.extend(self._get_branded_header(width_override=doc.width))
        
        # Document Title
        title_table = Table(
            [['QUICK SALE RECEIPT']],
            colWidths=[doc.width]
        )
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 2*mm))
        
        # Receipt Info
        receipt_data = [
            ['Receipt No:', f'QS-{sale.pk:05d}'],
            ['Date:', sale.date.strftime('%d/%m/%Y')],
        ]
        receipt_table = Table(receipt_data, colWidths=[70, 140])
        receipt_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY_BLUE),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (1, 0), (1, 0), 11),
        ]))
        elements.append(receipt_table)
        elements.append(Spacer(1, 2*mm))
        
        # Buyer Info (if provided)
        if sale.buyer_name or sale.buyer_phone:
            elements.append(Paragraph("SOLD TO:", self.styles['SectionHeader']))
            buyer_data = []
            if sale.buyer_name:
                buyer_data.append(['Name:', sale.buyer_name])
            if sale.buyer_phone:
                buyer_data.append(['Phone:', sale.buyer_phone])
            buyer_table = Table(buyer_data, colWidths=[60, 150])
            buyer_table.setStyle(TableStyle([
                *self._get_base_table_style(),
                ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
                ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
            ]))
            elements.append(buyer_table)
            elements.append(Spacer(1, 3*mm))
        
        # Sale Details
        elements.append(Paragraph("SALE DETAILS:", self.styles['SectionHeader']))
        
        subtotal = sale.quantity * sale.unit_price
        details_data = [
            ['Block Type:', sale.block_type.name],
            ['Quantity:', f'{sale.quantity} blocks'],
            ['Unit Price:', self._format_currency(sale.unit_price)],
            ['Subtotal:', self._format_currency(subtotal)],
        ]
        
        if sale.logistics_discount > 0:
            details_data.append(['Self-Pickup Discount:', f'-{self._format_currency(sale.logistics_discount)}/block'])
        
        details_table = Table(details_data, colWidths=[115, 95])
        details_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_NAVY),
            ('BOX', (0, 0), (-1, -1), 1, NAVY_BLUE),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 3*mm))
        
        # Amount Box (Gold Highlighted)
        elements.append(Paragraph("TOTAL PAID:", self.styles['SectionHeader']))
        
        amount_display = self._format_currency(sale.total_amount)
        amount_words = self._amount_in_words(sale.total_amount)
        
        amount_data = [
            [amount_display],
            [f"({amount_words})"],
        ]
        amount_table = Table(amount_data, colWidths=[doc.width])
        amount_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (0, 0), 22),
            ('FONTNAME', (0, 1), (0, 1), UNICODE_FONT),
            ('FONTSIZE', (0, 1), (0, 1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (0, 0), NAVY_BLUE),
            ('TEXTCOLOR', (0, 1), (0, 1), colors.gray),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GOLD),
            ('BOX', (0, 0), (-1, -1), 2, GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(amount_table)
        elements.append(Spacer(1, 2*mm))
        
        # Payment Details
        elements.append(Paragraph("PAYMENT:", self.styles['SectionHeader']))
        payment_data = [
            ['Method:', sale.get_payment_method_display()],
            ['Account:', sale.payment_account.bank_name],
        ]
        if sale.reference:
            payment_data.append(['Reference:', sale.reference])
        
        payment_table = Table(payment_data, colWidths=[80, 130])
        payment_table.setStyle(TableStyle([
            *self._get_base_table_style(),
            ('FONTNAME', (0, 0), (0, -1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(payment_table)
        
        # Remark
        if sale.remark:
            elements.append(Spacer(1, 2*mm))
            elements.append(Paragraph(f"<b>Remark:</b> {sale.remark}", self.styles['SmallText']))
        
        # Pickup Authorization
        if sale.pickup_authorized_by:
            elements.append(Spacer(1, 2*mm))
            elements.append(Paragraph(f"<b>Pickup Authorized By:</b> {sale.pickup_authorized_by}", self.styles['NormalText']))
        
        # Signature Section
        elements.append(Spacer(1, 5*mm))
        
        recorded_by_text = "Processed By: " + (sale.recorded_by.get_full_name() or sale.recorded_by.username if sale.recorded_by else 'N/A')
        
        sig_table_data = [
            ['', '', ''],
            [recorded_by_text, '', 'Authorized Signatory & Stamp']
        ]
        
        sig_table = Table(sig_table_data, colWidths=[doc.width*0.4, doc.width*0.2, doc.width*0.4])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 1), (-1, 1), UNICODE_FONT_BOLD),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('TEXTCOLOR', (0, 1), (-1, 1), NAVY_BLUE),
            ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),
            ('LINEABOVE', (2, 1), (2, 1), 1, colors.black),
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),
            ('ALIGN', (2, 1), (2, 1), 'RIGHT'),
            ('TOPPADDING', (0, 1), (-1, 1), 4),
            ('ROWHEIGHT', (0,0), (0,0), 15*mm),
        ]))
        elements.append(sig_table)
        
        # Footer
        elements.extend(self._get_footer())
        
        doc.build(elements)
        return self._create_response(buffer, f'QuickSale_QS-{sale.pk:05d}.pdf')