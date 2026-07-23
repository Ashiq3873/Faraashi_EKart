from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ====================== CONFIGURATION ======================
import tempfile

SECRET_KEY = 'faraashi-ekart-secret-key-2026'
MONGO_URI = 'mongodb+srv://AshiqDE:Ashiqkkdi01@ashiqde.cepcb.mongodb.net/?appName=AshiqDE'
CLOUDINARY_CLOUD_NAME = 'i8imsyyo'
CLOUDINARY_API_KEY = '912812412396134'
CLOUDINARY_API_SECRET = 'N6mo5Rl7DITKSDDTj-RfXOmS_tI'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'mohamedashiqb12@gmail.com')
ADMIN_EMAIL_PASSWORD = os.environ.get('ADMIN_EMAIL_PASSWORD', 'qmlf msyw dnhv mrdf').replace(' ', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

REVIEW_EXPRESSIONS = {
    'excellent': 'Excellent — Very Satisfied',
    'good': 'Good — Satisfied',
    'average': 'Average — Neutral',
    'poor': 'Poor — Unsatisfied',
    'disappointed': 'Very Disappointed',
}

TEMP_DIR = tempfile.gettempdir()

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.template_filter('format_datetime')
def format_datetime(value, fmt='%d %b %Y, %I:%M %p'):
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    return value

# MongoDB
db = None
try:
    client = MongoClient(MONGO_URI)
    db = client["faraashi_ekart"]
    print("[Mongo] MongoDB Connected!")
except Exception as e:
    print(f"[Mongo] MongoDB Error: {e}")

# Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Helper to query _id by string or ObjectId
def get_id_query(id_str):
    from bson.objectid import ObjectId
    try:
        return {"$or": [{"_id": id_str}, {"_id": ObjectId(id_str)}]}
    except Exception:
        return {"_id": id_str}

def get_product_stock(product):
    try:
        return max(int(product.get('stock', 0)), 0)
    except (TypeError, ValueError):
        return 0

def validate_cart_stock(cart_items):
    """Return list of stock error messages for cart items."""
    errors = []
    if db is None:
        return ['Store is temporarily unavailable. Please try again later.']

    for item in cart_items:
        product = db.products.find_one(get_id_query(item.get('_id')))
        qty = item.get('qty', 1)
        name = item.get('name', 'Product')

        if not product:
            errors.append(f'{name} is no longer available.')
            continue

        stock = get_product_stock(product)
        if stock < qty:
            if stock == 0:
                errors.append(f'{product.get("name", name)} is out of stock.')
            else:
                errors.append(f'Only {stock} unit(s) left for {product.get("name", name)}.')

    return errors

def reduce_product_stock(cart_items):
    """Reduce stock for each purchased item after order is saved."""
    for item in cart_items:
        db.products.update_one(
            get_id_query(item.get('_id')),
            {"$inc": {"stock": -item.get('qty', 1)}}
        )

def login_required_user():
    if not session.get('user'):
        flash('Please sign in to continue.', 'danger')
        return False
    return True

def send_email(to_email, subject, html_body, text_body=None):
    if not to_email:
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'Faraashi-Ekart <{ADMIN_EMAIL}>'
        msg['To'] = to_email
        msg.attach(MIMEText(text_body or html_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(ADMIN_EMAIL, ADMIN_EMAIL_PASSWORD)
            server.sendmail(ADMIN_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f'[Email Error] {e}')
        return False

def build_review_reply_email(review, ai_reply):
    user_name = review.get('user_name', 'Customer')
    target_name = review.get('target_name', 'your item')
    expression = review.get('expression_label', 'your feedback')
    review_text = review.get('review_text', '')

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 640px; margin: 0 auto; color: #0f172a;">
        <div style="background: linear-gradient(135deg, #6366f1, #059669); padding: 24px; border-radius: 12px 12px 0 0;">
            <h2 style="color: #fff; margin: 0;">Faraashi-Ekart — AI Customer Care</h2>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: none; padding: 24px; border-radius: 0 0 12px 12px;">
            <p>Dear <strong>{user_name}</strong>,</p>
            <p>Thank you for sharing your review about <strong>{target_name}</strong>.</p>
            <p style="background:#f8fafc; padding:12px 16px; border-left:4px solid #6366f1; border-radius:8px;">
                <strong>Your expression:</strong> {expression}<br/>
                <strong>Your review:</strong> {review_text}
            </p>
            <p><strong>AI Customer Care Response:</strong></p>
            <p style="background:#ecfdf5; padding:16px; border-radius:8px; border:1px solid #bbf7d0;">{ai_reply}</p>
            <p>If you need further assistance, reply to this email or contact us at {ADMIN_EMAIL}.</p>
            <p style="color:#64748b; font-size:14px; margin-top:24px;">Warm regards,<br/>Faraashi-Ekart Customer Care Team</p>
        </div>
    </div>
    """
    text_body = (
        f"Dear {user_name},\n\n"
        f"Thank you for your review about {target_name}.\n\n"
        f"Your expression: {expression}\n"
        f"Your review: {review_text}\n\n"
        f"AI Customer Care Response:\n{ai_reply}\n\n"
        f"Contact: {ADMIN_EMAIL}\n"
        f"Faraashi-Ekart Customer Care Team"
    )
    return html_body, text_body

def generate_fallback_review_reply(review):
    user_name = review.get('user_name', 'Customer')
    target_name = review.get('target_name', 'your purchase')
    review_type = review.get('review_type', 'product')
    expression = review.get('expression', 'average')
    item_label = 'product' if review_type == 'product' else 'article'

    templates = {
        'excellent': (
            f"Dear {user_name}, thank you so much for your wonderful review of our {item_label} \"{target_name}\". "
            f"We are delighted to know your experience was excellent. Your satisfaction motivates our entire team "
            f"to keep delivering premium quality and service. We look forward to serving you again at Faraashi-Ekart."
        ),
        'good': (
            f"Dear {user_name}, thank you for taking the time to review \"{target_name}\". "
            f"We appreciate your positive feedback and are glad the {item_label} met your expectations. "
            f"We will continue working to make every order even better. Thank you for choosing Faraashi-Ekart."
        ),
        'average': (
            f"Dear {user_name}, thank you for your honest review of \"{target_name}\". "
            f"We value your balanced feedback and take it seriously as we improve our {item_label}s and service. "
            f"If there is anything specific we can do better, our support team is always here to help at {ADMIN_EMAIL}."
        ),
        'poor': (
            f"Dear {user_name}, we sincerely apologize that your experience with \"{target_name}\" did not meet expectations. "
            f"Your feedback is important to us, and we are reviewing this internally to prevent similar issues. "
            f"Please contact us at {ADMIN_EMAIL} so we can make this right for you as quickly as possible."
        ),
        'disappointed': (
            f"Dear {user_name}, we are truly sorry to hear about your disappointing experience with \"{target_name}\". "
            f"This is not the standard we aim for at Faraashi-Ekart. We take full ownership of your concerns and "
            f"would like to resolve this personally — please reach out to us at {ADMIN_EMAIL} or call our support line."
        ),
    }
    return templates.get(expression, templates['average'])

def generate_ai_review_reply(review):
    user_name = review.get('user_name', 'Customer')
    target_name = review.get('target_name', 'item')
    review_type = review.get('review_type', 'product')
    expression = review.get('expression', 'average')
    expression_label = review.get('expression_label', REVIEW_EXPRESSIONS.get(expression, 'Neutral'))
    review_text = review.get('review_text', '')

    tone_instructions = {
        'excellent': 'Customer is very satisfied. Be warm, grateful, and encouraging.',
        'good': 'Customer is satisfied. Thank them and reinforce positive value.',
        'average': 'Customer is neutral. Acknowledge honestly and show commitment to improve.',
        'poor': 'Customer is unsatisfied. Apologize professionally and offer support.',
        'disappointed': 'Customer is very disappointed. Apologize sincerely, show empathy, and invite direct support contact.',
    }

    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are the AI customer care assistant for Faraashi-Ekart online store. '
                            'Write concise, empathetic, professional email replies to customer reviews. '
                            'Use 3-5 sentences. No subject line. No markdown. Sign off as Faraashi-Ekart Customer Care Team.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': (
                            f"Customer name: {user_name}\n"
                            f"Review type: {review_type}\n"
                            f"Item: {target_name}\n"
                            f"Customer expression: {expression_label}\n"
                            f"Tone guidance: {tone_instructions.get(expression, tone_instructions['average'])}\n"
                            f"Customer review: {review_text}\n\n"
                            f"Write a personalized reply based on their expression and review content."
                        ),
                    },
                ],
                max_tokens=280,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            if reply:
                return reply
        except Exception as e:
            print(f'[AI Reply Error] {e}')

    return generate_fallback_review_reply(review)

def process_review_with_ai(review_doc):
    ai_reply = generate_ai_review_reply(review_doc)
    review_doc['ai_reply'] = ai_reply
    review_doc['admin_reply'] = ai_reply
    review_doc['reply_source'] = 'ai'
    review_doc['replied_at'] = datetime.now()

    user_email = review_doc.get('user_email')
    if user_email:
        html_body, text_body = build_review_reply_email(review_doc, ai_reply)
        email_sent = send_email(
            user_email,
            f'Re: Your review on {review_doc.get("target_name", "Faraashi-Ekart")}',
            html_body,
            text_body,
        )
        review_doc['status'] = 'replied' if email_sent else 'pending'
        review_doc['email_sent'] = email_sent
    else:
        review_doc['status'] = 'pending'
        review_doc['email_sent'] = False

    return review_doc

# ====================== ROUTES ======================

@app.route('/')
def index():
    products = list(db.products.find()) if db is not None else []
    blogs = list(db.blogs.find().sort("created_at", -1).limit(3)) if db is not None else []
    
    categories = []
    if db is not None and products:
        categories = sorted(list(set(p.get('category', 'Uncategorized') for p in products)))
    
    return render_template('index.html', products=products, blogs=blogs, categories=categories)

@app.route('/products')
def products():
    category = request.args.get('category')
    if category and db is not None:
        prods = list(db.products.find({"category": category}))
    else:
        prods = list(db.products.find()) if db is not None else []
    return render_template('product.html', products=prods, selected_category=category)

@app.route('/blogs')
def blogs():
    category = request.args.get('category')
    if category and db is not None:
        blogs_list = list(db.blogs.find({"category": category}).sort("created_at", -1))
    else:
        blogs_list = list(db.blogs.find().sort("created_at", -1)) if db is not None else []
    return render_template('blogs.html', blogs=blogs_list, selected_category=category)

@app.route('/blog/<blog_id>')
def blog_detail(blog_id):
    if db is not None:
        blog = db.blogs.find_one(get_id_query(blog_id))
        if blog:
            return render_template('blog_detail.html', blog=blog)
    return redirect(url_for('blogs'))

@app.route('/product/<pid>')
def product_detail(pid):
    if db is not None:
        product = db.products.find_one(get_id_query(pid))
        if product:
            return render_template('product_detail.html', product=product)
    return redirect(url_for('products'))

@app.route('/add_to_cart/<pid>')
def add_to_cart(pid):
    if db is not None:
        product = db.products.find_one(get_id_query(pid))
        if product:
            stock = get_product_stock(product)
            if stock <= 0:
                flash(f'{product.get("name", "Product")} is out of stock.', 'danger')
                return redirect(request.referrer or url_for('products'))

            cart = session.get('cart', [])
            pid_str = str(product['_id'])
            current_qty = 0
            for item in cart:
                if str(item['_id']) == pid_str:
                    current_qty = item.get('qty', 1)
                    break

            if current_qty + 1 > stock:
                flash(f'Only {stock} unit(s) available for {product.get("name", "this product")}.', 'warning')
                return redirect(request.referrer or url_for('products'))

            for item in cart:
                if str(item['_id']) == pid_str:
                    item['qty'] = item.get('qty', 1) + 1
                    break
            else:
                p = dict(product)
                p['_id'] = pid_str
                p['qty'] = 1
                cart.append(p)
            session['cart'] = cart
            flash('Added to cart!', 'success')
    return redirect(request.referrer or url_for('products'))

@app.route('/update_cart/<pid>/<action>')
def update_cart(pid, action):
    cart = session.get('cart', [])
    new_cart = []
    for item in cart:
        if str(item['_id']) == pid:
            if action == 'increase':
                if db is not None:
                    product = db.products.find_one(get_id_query(pid))
                    stock = get_product_stock(product) if product else 0
                    next_qty = item.get('qty', 1) + 1
                    if next_qty > stock:
                        flash(f'Only {stock} unit(s) available for {item.get("name", "this product")}.', 'warning')
                        new_cart.append(item)
                        continue
                item['qty'] = item.get('qty', 1) + 1
                new_cart.append(item)
            elif action == 'decrease':
                qty = item.get('qty', 1) - 1
                if qty > 0:
                    item['qty'] = qty
                    new_cart.append(item)
                else:
                    flash(f"Removed {item.get('name')} from cart.", 'info')
            else:
                new_cart.append(item)
        else:
            new_cart.append(item)
    session['cart'] = new_cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    total = sum(item.get('price', 0) * item.get('qty', 1) for item in cart_items)
    return render_template('cart.html', cart=cart_items, total=total)

@app.route('/checkout')
def checkout():
    if not session.get('user'):
        flash('Please login or register to place an order.', 'danger')
        return redirect(url_for('login', next=request.path))
    cart_items = session.get('cart', [])
    if not cart_items:
        return redirect(url_for('products'))
    total = sum(item.get('price', 0) * item.get('qty', 1) for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/place_order', methods=['POST'])
def place_order():
    if not session.get('user'):
        flash('Please login or register to place an order.', 'danger')
        return redirect(url_for('login', next=url_for('checkout')))
        
    cart_items = session.get('cart', [])
    if not cart_items:
        return redirect(url_for('products'))

    stock_errors = validate_cart_stock(cart_items)
    if stock_errors:
        for message in stock_errors:
            flash(message, 'danger')
        return redirect(url_for('checkout'))
        
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')
    city = request.form.get('city')
    pin_code = request.form.get('pin_code')
    
    total = sum(item.get('price', 0) * item.get('qty', 1) for item in cart_items)
    order_id = str(datetime.now().timestamp())
    
    # Save order to DB and reduce stock
    if db is not None:
        try:
            db.orders.insert_one({
                "_id": order_id,
                "user_id": session['user']['_id'],
                "customer_name": f"{first_name} {last_name}",
                "email": email,
                "phone": phone,
                "address": f"{address}, {city} - {pin_code}",
                "items": cart_items,
                "total": total,
                "status": "C",
                "created_at": datetime.now()
            })
            reduce_product_stock(cart_items)
        except Exception as e:
            print(f"[Order Save Error] {e}")
            flash('Unable to place order. Please try again.', 'danger')
            return redirect(url_for('checkout'))
            
    # Clear the cart in the session
    session['cart'] = []
    
    flash('Order placed successfully!', 'success')
    return redirect(url_for('order_success', order_id=order_id))

@app.route('/order_success/<order_id>')
def order_success(order_id):
    if not session.get('user'):
        flash('Please login to view order details.', 'danger')
        return redirect(url_for('login'))
        
    if db is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('index'))
        
    order = db.orders.find_one(get_id_query(order_id))
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('index'))
        
    # Ensure authorization
    if order.get('user_id') != session['user']['_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    return render_template('order_success.html', order=order)

@app.route('/download_invoice/<order_id>')
def download_invoice(order_id):
    if not session.get('user'):
        flash('Please login to download the invoice.', 'danger')
        return redirect(url_for('login'))
        
    if db is None:
        flash('Database connection error.', 'danger')
        return redirect(url_for('index'))
        
    order = db.orders.find_one(get_id_query(order_id))
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('index'))
        
    # Ensure authorization
    if order.get('user_id') != session['user']['_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    # Generate Beautiful Premium Invoice PDF
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import urllib.request
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Premium Palette
    c_primary = colors.HexColor("#0F172A")    # Deep slate
    c_secondary = colors.HexColor("#6366F1")  # Brand Indigo accent
    c_text_dark = colors.HexColor("#1E293B")  # Muted slate text
    c_text_light = colors.HexColor("#64748B") # Muted gray text
    c_border = colors.HexColor("#E2E8F0")     # Border gray
    c_bg_light = colors.HexColor("#F8FAFC")   # Soft gray bg
    
    # Typography
    style_body = ParagraphStyle(
        'InvoiceBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_text_dark
    )
    
    style_body_bold = ParagraphStyle(
        'InvoiceBodyBold',
        parent=style_body,
        fontName='Helvetica-Bold'
    )
    
    style_header_label = ParagraphStyle(
        'HeaderLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.white
    )
    
    # Decorative Top Accent Bar
    top_bar = Table([[""]], colWidths=[540], rowHeights=[6])
    top_bar.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_secondary),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(top_bar)
    story.append(Spacer(1, 20))
    
    # 1. Header (Brand Info on left, Invoice metadata on right)
    brand_info = """
    <font size="16" color="#0F172A"><b>Faraashi Ekart</b></font><br/>
    <font color="#64748B">Karaikudi, Tamil Nadu, India<br/>
    Email: mohamedashiqb12@gmail.com<br/>
    Phone: +91 6385658696</font>
    """
    
    created_date = order.get('created_at')
    date_str = created_date.strftime('%d %b %Y, %I:%M %p') if hasattr(created_date, 'strftime') else str(created_date)
    
    meta_info = f"""
    <b>INVOICE</b><br/>
    <font color="#64748B">Order ID: #{order.get('_id').split('.')[0]}<br/>
    Date: {date_str}<br/>
    Payment Status: Paid (COD)</font>
    """
    
    header_table = Table([
        [Paragraph(brand_info.strip(), style_body), Paragraph(meta_info.strip(), style_body)]
    ], colWidths=[270, 270])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))
    
    # 2. Billing & Shipping Panels
    billing_info = f"""
    <b>BILLED TO:</b><br/>
    Name: {order.get('customer_name')}<br/>
    Email: {order.get('email')}<br/>
    Phone: {order.get('phone')}
    """
    
    shipping_info = f"""
    <b>SHIPPING TO:</b><br/>
    Address: {order.get('address')}<br/>
    Expected Delivery: 3-5 Business Days
    """
    
    billing_table = Table([
        [Paragraph(billing_info.strip(), style_body), Paragraph(shipping_info.strip(), style_body)]
    ], colWidths=[260, 260])
    
    billing_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('PADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    
    # Wrap in outer table for alignment/spacing
    billing_container = Table([[billing_table]], colWidths=[540])
    billing_container.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
    ]))
    story.append(billing_container)
    story.append(Spacer(1, 10))
    
    # 3. Items Table
    table_data = [
        [
            Paragraph("<b>Image</b>", style_header_label),
            Paragraph("<b>Description</b>", style_header_label),
            Paragraph("<b>Price</b>", style_header_label),
            Paragraph("<b>Qty</b>", style_header_label),
            Paragraph("<b>Amount</b>", style_header_label)
        ]
    ]
    
    for item in order.get('items', []):
        img_flowable = None
        img_url = item.get('image_url')
        if img_url and img_url.startswith('http'):
            try:
                req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    img_data = resp.read()
                    img_flowable = RLImage(io.BytesIO(img_data), width=30, height=30)
            except Exception:
                pass
                
        if not img_flowable:
            img_flowable = Paragraph("<font color='#94A3B8'>N/A</font>", style_body)
            
        desc_p = Paragraph(f"<b>{item.get('name')}</b><br/><font color='#64748B' size='8'>{item.get('category', '')}</font>", style_body)
        price_p = Paragraph(f"₹{item.get('price', 0):.2f}", style_body)
        qty_p = Paragraph(str(item.get('qty', 1)), style_body)
        amount_p = Paragraph(f"₹{item.get('price', 0) * item.get('qty', 1):.2f}", style_body)
        
        table_data.append([img_flowable, desc_p, price_p, qty_p, amount_p])
        
    items_table = Table(table_data, colWidths=[50, 260, 90, 50, 90])
    
    t_style = [
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (3,-1), 'CENTER'),
        ('ALIGN', (0,0), (1,-1), 'LEFT'),
    ]
    
    for i in range(1, len(table_data)):
        bg_col = c_bg_light if i % 2 == 0 else colors.white
        t_style.append(('BACKGROUND', (0,i), (-1,i), bg_col))
        t_style.append(('LINEBELOW', (0,i), (-1,i), 0.5, c_border))
        
    items_table.setStyle(TableStyle(t_style))
    story.append(items_table)
    story.append(Spacer(1, 15))
    
    # 4. Total Calculation Block
    subtotal = order.get('total', 0)
    delivery = 0.0 if subtotal >= 999 else 49.0
    grand_total = subtotal + delivery
    
    summary_table = Table([
        [Paragraph("Subtotal:", style_body), Paragraph(f"₹{subtotal:.2f}", style_body)],
        [Paragraph("Delivery:", style_body), Paragraph("FREE" if delivery == 0 else f"₹{delivery:.2f}", style_body)],
        [Paragraph("<b>Grand Total:</b>", style_body_bold), Paragraph(f"<b>₹{grand_total:.2f}</b>", style_body_bold)]
    ], colWidths=[120, 100])
    
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEABOVE', (0,2), (1,2), 1.5, c_primary),
    ]))
    
    outer_summary = Table([["", summary_table]], colWidths=[320, 220])
    outer_summary.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(outer_summary)
    story.append(Spacer(1, 30))
    
    # 5. Thank You Panel
    thanks_text = """
    <font color="#0F172A"><b>Thank you for your business!</b></font><br/>
    If you have any questions about this invoice, please contact support at mohamedashiqb12@gmail.com.<br/>
    <i>Faraashi Ekart - Shop Premium.</i>
    """
    thanks_p = Paragraph(thanks_text.strip(), ParagraphStyle(
        'ThanksText',
        parent=style_body,
        alignment=1, # Center
        fontSize=9,
        leading=13,
        textColor=c_text_light
    ))
    
    footer_table = Table([[thanks_p]], colWidths=[540])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('PADDING', (0,0), (-1,-1), 12),
        ('BOX', (0,0), (-1,-1), 1, c_border),
    ]))
    story.append(KeepTogether(footer_table))
    
    doc.build(story)
    buffer.seek(0)
    
    session['cart'] = []
    
    from flask import send_file
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'invoice_{order_id.split(".")[0]}.pdf',
        mimetype='application/pdf'
    )

@app.route('/support')
def support():
    tab = request.args.get('tab', 'help')
    orders = []
    if session.get('user') and db is not None:
        orders = list(db.orders.find({"user_id": session['user']['_id']}).sort("created_at", -1))
    return render_template('support.html', tab=tab, orders=orders)

@app.context_processor
def inject_cart_count():
    cart = session.get('cart', [])
    count = sum(item.get('qty', 1) for item in cart)
    return dict(cart_count=count)

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        if username == 'admin' and password == 'admin123':
            session['is_admin'] = True
            flash('Admin Login Successful!', 'success')
            return redirect(url_for('admin_dashboard'))
            
        if db is not None:
            user = db.users.find_one({"username": username})
            if user and check_password_hash(user['password_hash'], password):
                session['user'] = {
                    "_id": user['_id'],
                    "username": user['username'],
                    "email": user['email']
                }
                flash(f"Welcome back, {user['username']}!", 'success')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('index'))
                
        flash('Invalid credentials', 'danger')
    return render_template('login.html', next=next_page)

@app.route('/register', methods=['GET', 'POST'])
def register():
    next_page = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        
        if db is not None:
            existing = db.users.find_one({"$or": [{"username": username}, {"email": email}]})
            if existing:
                flash('Username or Email already registered!', 'danger')
                return render_template('register.html', next=next_page)
            
            db.users.insert_one({
                "_id": str(datetime.now().timestamp()),
                "username": username,
                "email": email,
                "password_hash": generate_password_hash(password),
                "created_at": datetime.now()
            })
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login', next=next_page))
            
    return render_template('register.html', next=next_page)

@app.route('/admin/delete_product/<pid>')
def delete_product(pid):
    if not session.get('is_admin') or db is None:
        return redirect(url_for('login'))
    db.products.delete_one(get_id_query(pid))
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_blog/<bid>')
def delete_blog(bid):
    if not session.get('is_admin') or db is None:
        return redirect(url_for('login'))
    db.blogs.delete_one(get_id_query(bid))
    flash('Blog deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    products = list(db.products.find()) if db is not None else []
    blogs = list(db.blogs.find().sort("created_at", -1)) if db is not None else []
    orders = list(db.orders.find().sort("created_at", -1)) if db is not None else []

    low_stock_count = sum(1 for p in products if 0 < get_product_stock(p) <= 5)
    out_of_stock_count = sum(1 for p in products if get_product_stock(p) <= 0)
    pending_orders = sum(1 for o in orders if o.get('status') != 'D')
    total_revenue = sum(o.get('total', 0) for o in orders)
    reviews = list(db.reviews.find().sort("created_at", -1)) if db is not None else []
    pending_reviews = sum(1 for r in reviews if r.get('status') != 'replied')

    return render_template(
        'admin/dashboard.html',
        products=products,
        blogs=blogs,
        orders=orders,
        reviews=reviews,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        pending_orders=pending_orders,
        pending_reviews=pending_reviews,
        total_revenue=total_revenue,
        now=datetime.now(),
        review_expressions=REVIEW_EXPRESSIONS,
    )

@app.route('/admin/update_order_status/<order_id>/<status>')
def update_order_status(order_id, status):
    if not session.get('is_admin') or db is None:
        return redirect(url_for('login'))
    
    if status in ['C', 'P', 'S', 'D']:
        order = db.orders.find_one(get_id_query(order_id))
        if not order:
            flash('Order not found.', 'danger')
        elif order.get('status') == 'D':
            flash('Delivered orders cannot be updated. Delete the order if needed.', 'warning')
        else:
            db.orders.update_one(get_id_query(order_id), {"$set": {"status": status}})
            flash('Order status updated successfully!', 'success')
    else:
        flash('Invalid status code.', 'danger')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_order/<order_id>')
def admin_delete_order(order_id):
    if not session.get('is_admin') or db is None:
        return redirect(url_for('login'))

    order = db.orders.find_one(get_id_query(order_id))
    if not order:
        flash('Order not found.', 'danger')
    elif order.get('status') != 'D':
        flash('Only delivered orders can be deleted.', 'danger')
    else:
        db.orders.delete_one(get_id_query(order_id))
        flash('Order deleted successfully!', 'success')

    return redirect(url_for('admin_dashboard'))

@app.route('/delete_order/<order_id>')
def delete_order(order_id):
    if not session.get('user') or db is None:
        return redirect(url_for('login', next=url_for('support', tab='track')))

    order = db.orders.find_one(get_id_query(order_id))
    if not order:
        flash('Order not found.', 'danger')
    elif order.get('user_id') != session['user']['_id']:
        flash('You are not allowed to delete this order.', 'danger')
    elif order.get('status') != 'D':
        flash('You can delete an order only after it is delivered.', 'danger')
    else:
        db.orders.delete_one(get_id_query(order_id))
        flash('Order removed from your history.', 'success')

    return redirect(url_for('support', tab='track'))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if not session.get('is_admin') or db is None:
        return redirect(url_for('login'))

    image_url = "https://via.placeholder.com/400"
    image = request.files.get('image')
    if image and image.filename:
        try:
            result = cloudinary.uploader.upload(image)
            image_url = result['secure_url']
        except Exception:
            pass

    db.products.insert_one({
        "_id": str(datetime.now().timestamp()),
        "name": request.form['name'],
        "description": request.form['description'],
        "price": float(request.form['price']),
        "compare_price": float(request.form['compare_price']) if request.form.get('compare_price') else None,
        "category": request.form['category'],
        "image_url": image_url,
        "stock": int(request.form.get('stock', 10))
    })
    flash('Item Added Successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_blog', methods=['POST'])
def add_blog():
    if not session.get('is_admin') or db is None:
        return redirect(url_for('login'))

    image_url = None
    image = request.files.get('blog_image')
    if image and image.filename:
        try:
            result = cloudinary.uploader.upload(image)
            image_url = result['secure_url']
        except Exception:
            pass

    db.blogs.insert_one({
        "_id": str(datetime.now().timestamp()),
        "title": request.form['title'],
        "category": request.form['category'],
        "content": request.form['content'],
        "image_url": image_url,
        "author": "Admin",
        "created_at": datetime.now().strftime("%B %d, %Y")
    })
    flash('Blog Added Successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/reviews')
def reviews_hub():
    if not login_required_user():
        return redirect(url_for('login', next=url_for('reviews_hub')))
    return render_template('reviews/index.html')

@app.route('/reviews/products')
def review_products():
    if not login_required_user():
        return redirect(url_for('login', next=url_for('review_products')))
    products = list(db.products.find()) if db is not None else []
    return render_template('reviews/products.html', products=products)

@app.route('/reviews/blogs')
def review_blogs():
    if not login_required_user():
        return redirect(url_for('login', next=url_for('review_blogs')))
    blogs = list(db.blogs.find().sort("created_at", -1)) if db is not None else []
    return render_template('reviews/blogs.html', blogs=blogs)

@app.route('/reviews/write/<review_type>/<target_id>', methods=['GET', 'POST'])
def write_review(review_type, target_id):
    if not login_required_user():
        return redirect(url_for('login', next=url_for('write_review', review_type=review_type, target_id=target_id)))

    if db is None:
        flash('Store is temporarily unavailable.', 'danger')
        return redirect(url_for('reviews_hub'))

    if review_type not in ('product', 'blog'):
        flash('Invalid review type.', 'danger')
        return redirect(url_for('reviews_hub'))

    collection = db.products if review_type == 'product' else db.blogs
    target = collection.find_one(get_id_query(target_id))
    if not target:
        flash('Selected item was not found.', 'danger')
        return redirect(url_for('reviews_hub'))

    target_name = target.get('name') if review_type == 'product' else target.get('title')

    if request.method == 'POST':
        expression = request.form.get('expression', '').strip()
        review_text = request.form.get('review_text', '').strip()

        if expression not in REVIEW_EXPRESSIONS:
            flash('Please select how you feel about this item.', 'danger')
            return redirect(url_for('write_review', review_type=review_type, target_id=target_id))

        if len(review_text) < 20:
            flash('Please write a detailed review (at least 20 characters).', 'danger')
            return redirect(url_for('write_review', review_type=review_type, target_id=target_id))

        user = session['user']
        review_doc = {
            "_id": str(datetime.now().timestamp()),
            "user_id": user['_id'],
            "user_name": user['username'],
            "user_email": user.get('email', ''),
            "review_type": review_type,
            "target_id": str(target['_id']),
            "target_name": target_name,
            "expression": expression,
            "expression_label": REVIEW_EXPRESSIONS[expression],
            "review_text": review_text,
            "created_at": datetime.now(),
        }

        review_doc = process_review_with_ai(review_doc)
        db.reviews.insert_one(review_doc)

        ai_reply = review_doc.get('ai_reply', '')
        admin_html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>New Customer Review — AI Reply Sent</h2>
            <p><strong>From:</strong> {user['username']} ({user.get('email', 'No email')})</p>
            <p><strong>Type:</strong> {review_type.title()}</p>
            <p><strong>Item:</strong> {target_name}</p>
            <p><strong>Expression:</strong> {REVIEW_EXPRESSIONS[expression]}</p>
            <p><strong>Review:</strong> {review_text}</p>
            <p><strong>AI Auto-Reply:</strong> {ai_reply}</p>
            <p>Email delivered: {'Yes' if review_doc.get('email_sent') else 'No — check mail settings'}</p>
        </div>
        """
        send_email(
            ADMIN_EMAIL,
            f'[AI Handled] Review: {target_name} — Faraashi-Ekart',
            admin_html,
            f"Review from {user['username']} about {target_name}.\n\nAI Reply:\n{ai_reply}"
        )

        if review_doc.get('email_sent'):
            flash('Thank you! Your review was submitted and an AI response has been sent to your email.', 'success')
        else:
            flash('Review submitted. AI response was generated but email delivery failed — our team will follow up.', 'warning')
        return redirect(url_for('reviews_hub'))

    return render_template(
        'reviews/write.html',
        review_type=review_type,
        target=target,
        target_name=target_name,
        review_expressions=REVIEW_EXPRESSIONS,
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)