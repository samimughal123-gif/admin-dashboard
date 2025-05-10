from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
import os
import json
import uuid
import shutil
import pickle
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = 'agency_admin_secret_key'  # Change this to a secure random key in production

# File upload configuration
# Use a single, simple shared directory for all portfolio images
PORTFOLIO_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'portfolio_images')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['PORTFOLIO_FOLDER'] = PORTFOLIO_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create portfolio directory if it doesn't exist
os.makedirs(PORTFOLIO_FOLDER, exist_ok=True)

# Print the portfolio folder path for debugging
print(f"[ADMIN] Using portfolio folder: {PORTFOLIO_FOLDER}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_sync_script():
    """Run the auto_sync_portfolio.py script to sync portfolio items to the app"""
    import os
    import sys
    import subprocess

    # Get the path to the auto_sync_portfolio.py script
    sync_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auto_sync_portfolio.py")

    if os.path.exists(sync_script_path):
        # Run the sync script
        result = subprocess.run([sys.executable, sync_script_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True)
        print(f"Running portfolio sync script: {sync_script_path}")
        print(f"Sync script output: {result.stdout}")
        if result.stderr:
            print(f"Sync script error: {result.stderr}")
        return True
    else:
        print(f"Sync script not found: {sync_script_path}")
        return False

# Database storage with SQLite
class DatabaseStorage:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin_panel.db')
        self._create_tables()

        # Initialize users if needed
        self._init_users()

        # Portfolio items (still in memory for simplicity)
        self.portfolio_items = []
        self._load_portfolio_items()

        # Create sample portfolio images
        self._create_sample_portfolio_images()

        # Save portfolio items to pickle file for sync script
        self._save_portfolio_items_to_pickle()

    def _create_tables(self):
        """Create the necessary tables if they don't exist"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
        ''')

        # Orders table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            service_name TEXT NOT NULL,
            requirements TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Contact messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Portfolio items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            image_filename TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()

    def _init_users(self):
        """Initialize admin user if not exists"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if admin user exists
        cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
        if cursor.fetchone()[0] == 0:
            # Create admin user
            cursor.execute(
                'INSERT INTO users (username, password, name, is_admin) VALUES (?, ?, ?, ?)',
                ('admin', 'admin', 'Administrator', 1)
            )
            conn.commit()
            print("Created admin user")

        conn.close()

    def _load_portfolio_items(self):
        """Load portfolio items from database or initialize with defaults"""
        # Initialize contact messages
        self.contact_messages = [
            {
                'id': 1,
                'name': 'Mike Wilson',
                'email': 'mike@example.com',
                'subject': 'Pricing Question',
                'message': 'Can you provide pricing for your services?',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'id': 2,
                'name': 'Sarah Lee',
                'email': 'sarah@example.com',
                'subject': 'Consultation Request',
                'message': 'I would like to schedule a consultation',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        ]

        # Load portfolio items from database
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if portfolio_items table exists and has data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio_items'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM portfolio_items")
            count = cursor.fetchone()[0]

            if count > 0:
                # Load portfolio items from database
                cursor.execute("SELECT * FROM portfolio_items ORDER BY id")
                self.portfolio_items = [dict(row) for row in cursor.fetchall()]
                print(f"Loaded {len(self.portfolio_items)} portfolio items from database")
                conn.close()
                return

        # If no items in database, initialize with defaults
        default_items = [
            {
                'title': 'Business Cards & Brochures',
                'description': 'Professional printing services for all your business needs including business cards, brochures, banners, and more.',
                'category': 'Printing Press',
                'image_filename': 'printing_press_brochure.jpg',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'title': 'Search Engine Optimization',
                'description': 'Comprehensive SEO services to improve your website\'s visibility in search engine results and drive more organic traffic.',
                'category': 'SEO',
                'image_filename': 'seo_optimization_service.jpg',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'title': 'Basic Package',
                'description': 'Affordable solution for small businesses including basic design services and essential marketing tools.',
                'category': 'Packages Solutions',
                'image_filename': 'packages_solution_basic.jpg',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        ]

        # Insert default items into database
        for item in default_items:
            cursor.execute(
                "INSERT INTO portfolio_items (title, description, category, image_filename, created_at) VALUES (?, ?, ?, ?, ?)",
                (item['title'], item['description'], item['category'], item['image_filename'], item['created_at'])
            )

        conn.commit()

        # Get the inserted items with their IDs
        cursor.execute("SELECT * FROM portfolio_items ORDER BY id")
        self.portfolio_items = [dict(row) for row in cursor.fetchall()]
        print(f"Initialized {len(self.portfolio_items)} default portfolio items in database")

        conn.close()

    def get_user(self, username, password):
        """Get a user by username and password"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()

        conn.close()
        return dict(user) if user else None

    def get_orders(self, status=None):
        """Get orders from the database, optionally filtered by status"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status:
            cursor.execute('SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC', (status,))
        else:
            cursor.execute('SELECT * FROM orders ORDER BY created_at DESC')

        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders

    def get_order(self, order_id):
        """Get a specific order by ID"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()

        conn.close()
        return dict(order) if order else None

    def update_order_status(self, order_id, status):
        """Update the status of an order"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()

        success = cursor.rowcount > 0
        conn.close()
        return success

    def get_contact_messages(self):
        """Get all contact messages"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM contact_messages ORDER BY created_at DESC')
        messages = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return messages

    def _create_sample_portfolio_images(self):
        """Create sample portfolio images if they don't exist"""
        # Create simple colored rectangles as sample images
        from PIL import Image, ImageDraw, ImageFont

        # Define colors and filenames for each service
        # Using clear service prefixes to ensure proper categorization in the mobile app
        service_images = [
            ('printing_press_brochure.jpg', (200, 50, 50)),       # Dark red for Printing Press
            ('seo_optimization_service.jpg', (200, 150, 50)),     # Orange for SEO
            ('packages_solution_basic.jpg', (50, 100, 150))       # Blue for Basic Package
            # Removed Premium Package to ensure only one item per category
        ]

        # First, check if any images exist in the portfolio folder
        existing_images = [f for f in os.listdir(app.config['PORTFOLIO_FOLDER'])
                          if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]

        # If we have at least one image for each service category, don't create new ones
        if existing_images:
            print(f"Found {len(existing_images)} existing images in portfolio folder, preserving them")

            # Check if we have at least one image for each service
            has_printing = any('print' in img.lower() for img in existing_images)
            has_seo = any('seo' in img.lower() for img in existing_images)
            has_packages = any('package' in img.lower() or 'solution' in img.lower() for img in existing_images)

            # If we have all three service types represented, return early
            if has_printing and has_seo and has_packages:
                print("All service categories have images, skipping sample image creation")
                return

            # Otherwise, only create images for missing service categories
            service_images = [
                (filename, color) for filename, color in service_images
                if ('print' in filename.lower() and not has_printing) or
                   ('seo' in filename.lower() and not has_seo) or
                   (('package' in filename.lower() or 'solution' in filename.lower()) and not has_packages)
            ]

            if not service_images:
                print("No new sample images needed")
                return

        for filename, color in service_images:
            filepath = os.path.join(app.config['PORTFOLIO_FOLDER'], filename)

            # Skip if file already exists
            if os.path.exists(filepath):
                print(f"Sample image already exists: {filepath}")
                continue

            # Create a colored image
            img = Image.new('RGB', (400, 250), color=color)
            draw = ImageDraw.Draw(img)

            # Add a white border
            draw.rectangle([10, 10, 390, 240], outline=(255, 255, 255), width=5)

            # Add a simple icon or design element in the center (instead of text)
            try:
                # Draw a simple design element (circle)
                center_x, center_y = 200, 125
                radius = 50
                draw.ellipse((center_x - radius, center_y - radius,
                             center_x + radius, center_y + radius),
                             outline=(255, 255, 255), width=3)

                # Draw a smaller inner circle with the service color but brighter
                inner_radius = 30
                r, g, b = color
                brighter_color = (min(r + 50, 255), min(g + 50, 255), min(b + 50, 255))
                draw.ellipse((center_x - inner_radius, center_y - inner_radius,
                             center_x + inner_radius, center_y + inner_radius),
                             fill=brighter_color, outline=(255, 255, 255), width=1)
            except Exception as e:
                print(f"Error adding design element to image: {e}")

            # Save the image
            img.save(filepath, 'JPEG')
            print(f"Created sample image: {filepath}")

    def get_portfolio_items(self):
        """Get all portfolio items"""
        return self.portfolio_items

    def get_portfolio_item(self, item_id):
        """Get a portfolio item by ID"""
        for item in self.portfolio_items:
            if item['id'] == item_id:
                return item
        return None

    def add_portfolio_item(self, title, description, category, image_filename):
        """Add a new portfolio item"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Normalize category to match app's service names
        normalized_category = category
        if category.lower() not in ['printing press', 'seo', 'packages solutions']:
            # Map to one of the three valid categories
            if 'print' in category.lower() or 'press' in category.lower():
                normalized_category = 'Printing Press'
            elif 'seo' in category.lower() or 'search' in category.lower():
                normalized_category = 'SEO'
            elif 'package' in category.lower() or 'solution' in category.lower():
                normalized_category = 'Packages Solutions'
            else:
                # Default to Printing Press if no match
                normalized_category = 'Printing Press'

            print(f"Normalized category from '{category}' to '{normalized_category}'")

        # Delete existing portfolio items and images for this category from database
        cursor.execute("SELECT * FROM portfolio_items WHERE LOWER(category) = LOWER(?)", (normalized_category,))
        items_to_delete = cursor.fetchall()

        for item in items_to_delete:
            # Delete the image file
            try:
                old_image = item['image_filename']
                old_path = os.path.join(app.config['PORTFOLIO_FOLDER'], old_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
                    print(f"Deleted old image from shared directory: {old_path}")
            except Exception as e:
                print(f"Error removing old image: {e}")

            # Delete the item from database
            cursor.execute("DELETE FROM portfolio_items WHERE id = ?", (item['id'],))
            print(f"Deleted existing portfolio item (ID: {item['id']}) for category: {normalized_category}")

        # Insert new portfolio item into database
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO portfolio_items (title, description, category, image_filename, created_at) VALUES (?, ?, ?, ?, ?)",
            (title, description, normalized_category, image_filename, created_at)
        )

        # Get the inserted item ID
        new_id = cursor.lastrowid

        # Commit changes
        conn.commit()

        # Get the inserted item
        cursor.execute("SELECT * FROM portfolio_items WHERE id = ?", (new_id,))
        new_item = dict(cursor.fetchone())

        # Close connection
        conn.close()

        # Update in-memory list
        # First remove any items with the same category
        self.portfolio_items = [item for item in self.portfolio_items if item['category'].lower() != normalized_category.lower()]
        # Then add the new item
        self.portfolio_items.append(new_item)

        # Save portfolio items to pickle file for sync script
        self._save_portfolio_items_to_pickle()

        # No need to copy the image to the app's assets directory anymore
        # since we're using a shared directory structure
        print(f"Image saved to shared portfolio directory: {image_filename}")
        print(f"This is a {normalized_category} portfolio item")

        return new_item

    def _save_portfolio_items_to_pickle(self):
        """Save portfolio items to a pickle file for the sync script"""
        try:
            pickle_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_items.pickle")
            with open(pickle_path, "wb") as f:
                pickle.dump(self.portfolio_items, f)
            print(f"Saved {len(self.portfolio_items)} portfolio items to pickle file")
        except Exception as e:
            print(f"Error saving portfolio items to pickle file: {e}")

    def update_portfolio_item(self, item_id, title, description, category, image_filename=None):
        """Update an existing portfolio item"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get the item we're updating from database
        cursor.execute("SELECT * FROM portfolio_items WHERE id = ?", (item_id,))
        target_item = cursor.fetchone()

        if not target_item:
            conn.close()
            return None

        # Convert to dict for easier handling
        target_item = dict(target_item)

        # Store the original category for comparison
        original_category = target_item['category']

        # Normalize category to match app's service names
        normalized_category = category
        if category.lower() not in ['printing press', 'seo', 'packages solutions']:
            # Map to one of the three valid categories
            if 'print' in category.lower() or 'press' in category.lower():
                normalized_category = 'Printing Press'
            elif 'seo' in category.lower() or 'search' in category.lower():
                normalized_category = 'SEO'
            elif 'package' in category.lower() or 'solution' in category.lower():
                normalized_category = 'Packages Solutions'
            else:
                # Default to Printing Press if no match
                normalized_category = 'Printing Press'

            print(f"Normalized category from '{category}' to '{normalized_category}'")

        # If the category has changed or a new image is provided, we need to handle other items
        if original_category.lower() != normalized_category.lower() or image_filename:
            # Delete all other items in the same category from database
            cursor.execute("SELECT * FROM portfolio_items WHERE LOWER(category) = LOWER(?) AND id != ?",
                          (normalized_category, item_id))
            items_to_delete = cursor.fetchall()

            for item in items_to_delete:
                # Delete the image file
                try:
                    old_image = item['image_filename']
                    old_path = os.path.join(app.config['PORTFOLIO_FOLDER'], old_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                        print(f"Deleted old image from shared directory: {old_path}")
                except Exception as e:
                    print(f"Error removing old image: {e}")

                # Delete the item from database
                cursor.execute("DELETE FROM portfolio_items WHERE id = ?", (item['id'],))
                print(f"Deleted existing portfolio item (ID: {item['id']}) for category: {normalized_category}")

        # Handle the image update for the current item
        if image_filename:
            # If there's a previous image and it's different from the new one, delete it
            old_image = target_item['image_filename']
            if old_image != image_filename:
                try:
                    # Delete the old image from the shared directory
                    old_path = os.path.join(app.config['PORTFOLIO_FOLDER'], old_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                        print(f"Deleted old image from shared directory: {old_path}")
                        print(f"This was a {normalized_category} portfolio item")
                except Exception as e:
                    print(f"Error removing old image: {e}")

            # Update the image filename in the database
            cursor.execute(
                "UPDATE portfolio_items SET title = ?, description = ?, category = ?, image_filename = ? WHERE id = ?",
                (title, description, normalized_category, image_filename, item_id)
            )
        else:
            # Update without changing the image
            cursor.execute(
                "UPDATE portfolio_items SET title = ?, description = ?, category = ? WHERE id = ?",
                (title, description, normalized_category, item_id)
            )

        # Commit changes
        conn.commit()

        # Get the updated item
        cursor.execute("SELECT * FROM portfolio_items WHERE id = ?", (item_id,))
        updated_item = dict(cursor.fetchone())

        # Close connection
        conn.close()

        # Update in-memory list
        # First remove any items with the same category (except the one we're updating)
        self.portfolio_items = [item for item in self.portfolio_items
                               if not (item['category'].lower() == normalized_category.lower() and item['id'] != item_id)]

        # Then update the current item in the list
        for i, item in enumerate(self.portfolio_items):
            if item['id'] == item_id:
                self.portfolio_items[i] = updated_item
                break
        else:
            # If the item wasn't found in the list, add it
            self.portfolio_items.append(updated_item)

        # Save portfolio items to pickle file for sync script
        self._save_portfolio_items_to_pickle()

        print(f"Updated portfolio item: {updated_item['title']} (ID: {updated_item['id']})")
        if image_filename:
            print(f"Image updated in shared portfolio directory: {image_filename}")

        return updated_item

    def delete_portfolio_item(self, item_id):
        """Delete a portfolio item"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get the item from database
        cursor.execute("SELECT * FROM portfolio_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            conn.close()
            return False

        # Convert to dict for easier handling
        item = dict(item)

        # Get the category for logging
        category = item.get('category', 'Unknown')

        # Delete the image file from the shared directory
        try:
            # The image is now in the shared directory, which is linked to both
            # the admin panel and app directories
            image_path = os.path.join(app.config['PORTFOLIO_FOLDER'], item['image_filename'])
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image from shared directory: {image_path}")
                print(f"This was a {category} portfolio item")
        except Exception as e:
            print(f"Error removing image: {e}")

        # Delete the item from database
        cursor.execute("DELETE FROM portfolio_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

        # Remove the item from the in-memory list
        for i, list_item in enumerate(self.portfolio_items):
            if list_item['id'] == item_id:
                del self.portfolio_items[i]
                break

        # Save portfolio items to pickle file for sync script
        self._save_portfolio_items_to_pickle()

        print(f"Deleted portfolio item (ID: {item_id})")
        return True

# Create storage instance
db = DatabaseStorage()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')

        user = db.get_user(username, password)

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get counts for dashboard
    pending_orders = len(db.get_orders(status='pending'))
    in_progress_orders = len(db.get_orders(status='in_progress'))
    completed_orders = len(db.get_orders(status='completed'))

    # Get recent orders
    recent_orders = db.get_orders()[:5]

    # Get contact messages
    contact_messages = db.get_contact_messages()[:5]

    # Get portfolio items
    portfolio_items = db.get_portfolio_items()

    return render_template('dashboard.html',
                          pending_orders=pending_orders,
                          in_progress_orders=in_progress_orders,
                          completed_orders=completed_orders,
                          recent_orders=recent_orders,
                          contact_messages=contact_messages,
                          portfolio_items=portfolio_items)

@app.route('/orders')
@login_required
def orders():
    status_filter = request.args.get('status', '')

    if status_filter and status_filter != 'all':
        orders = db.get_orders(status=status_filter)
    else:
        orders = db.get_orders()

    return render_template('orders.html', orders=orders, current_filter=status_filter)

@app.route('/orders/<int:order_id>')
@login_required
def view_order(order_id):
    order = db.get_order(order_id)

    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('orders'))

    return render_template('order_details.html', order=order)

@app.route('/orders/<int:order_id>/update', methods=['POST'])
@login_required
def update_order(order_id):
    status = request.form.get('status')

    if not status:
        flash('Please select a status', 'error')
        return redirect(url_for('view_order', order_id=order_id))

    success = db.update_order_status(order_id, status)

    if success:
        flash('Order status updated successfully', 'success')
    else:
        flash('Failed to update order status', 'error')

    return redirect(url_for('view_order', order_id=order_id))

@app.route('/api/check-notifications')
@login_required
def check_notifications():
    # Get count of new orders (pending status)
    pending_orders = len(db.get_orders(status='pending'))

    return jsonify({
        'pending_orders': pending_orders
    })

# Portfolio management routes
@app.route('/portfolio')
@login_required
def portfolio():
    portfolio_items = db.get_portfolio_items()
    return render_template('portfolio.html', portfolio_items=portfolio_items)

@app.route('/portfolio/add', methods=['GET', 'POST'])
@login_required
def add_portfolio():
    # Import modules at the function level to avoid scope issues
    import os
    import uuid

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')

        if not title or not description or not category:
            flash('Please fill in all required fields', 'error')
            return render_template('portfolio_form.html')

        # Check if an image was uploaded
        if 'image' not in request.files:
            flash('No image file uploaded', 'error')
            return render_template('portfolio_form.html')

        image_file = request.files['image']

        if image_file.filename == '':
            flash('No image file selected', 'error')
            return render_template('portfolio_form.html')

        if image_file and allowed_file(image_file.filename):
            # Generate a unique filename
            filename = secure_filename(image_file.filename)
            filename = f"{uuid.uuid4().hex}_{filename}"

            # Save the file
            image_path = os.path.join(app.config['PORTFOLIO_FOLDER'], filename)
            image_file.save(image_path)

            # Add the portfolio item
            db.add_portfolio_item(title, description, category, filename)

            # Sync portfolio items to app database
            try:
                # Run the sync function directly
                run_sync_script()
            except Exception as e:
                print(f"Error running portfolio sync script: {e}")

            flash('Portfolio item added successfully', 'success')
            return redirect(url_for('portfolio'))
        else:
            flash('Invalid file type. Allowed types: jpg, jpeg, png, gif', 'error')

    return render_template('portfolio_form.html')

@app.route('/portfolio/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_portfolio(item_id):
    # Import modules at the function level to avoid scope issues
    import os
    import uuid

    portfolio_item = db.get_portfolio_item(item_id)

    if not portfolio_item:
        flash('Portfolio item not found', 'error')
        return redirect(url_for('portfolio'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')

        if not title or not description or not category:
            flash('Please fill in all required fields', 'error')
            return render_template('portfolio_form.html', portfolio_item=portfolio_item)

        # Check if a new image was uploaded
        image_filename = None  # Initialize to None by default
        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']

            if allowed_file(image_file.filename):
                # Generate a unique filename
                filename = secure_filename(image_file.filename)
                filename = f"{uuid.uuid4().hex}_{filename}"

                # Save the file
                image_path = os.path.join(app.config['PORTFOLIO_FOLDER'], filename)
                image_file.save(image_path)

                # Set the image filename to be used in the update
                image_filename = filename
            else:
                flash('Invalid file type. Allowed types: jpg, jpeg, png, gif', 'error')
                return render_template('portfolio_form.html', portfolio_item=portfolio_item)

        # Update the portfolio item
        db.update_portfolio_item(item_id, title, description, category, image_filename)

        # Sync portfolio items to app database
        try:
            # Run the sync function directly
            run_sync_script()
        except Exception as e:
            print(f"Error running portfolio sync script: {e}")

        flash('Portfolio item updated successfully', 'success')
        return redirect(url_for('portfolio'))

    return render_template('portfolio_form.html', portfolio_item=portfolio_item)

@app.route('/portfolio/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_portfolio(item_id):

    success = db.delete_portfolio_item(item_id)

    if success:
        # Sync portfolio items to app database
        try:
            # Run the sync function directly
            run_sync_script()
        except Exception as e:
            print(f"Error running portfolio sync script: {e}")

        flash('Portfolio item deleted successfully', 'success')
    else:
        flash('Failed to delete portfolio item', 'error')

    return redirect(url_for('portfolio'))

@app.route('/uploads/portfolio/<filename>')
def portfolio_image(filename):
    """Serve portfolio images from the shared directory"""
    # Check if the file exists in the shared directory
    if os.path.exists(os.path.join(app.config['PORTFOLIO_FOLDER'], filename)):
        return send_from_directory(app.config['PORTFOLIO_FOLDER'], filename)
    else:
        # If not found, try to create a sample image
        try:
            # Create a sample image
            from PIL import Image, ImageDraw

            # Determine color based on filename
            if 'printing' in filename.lower():
                color = (200, 50, 50)  # Red for Printing Press
            elif 'seo' in filename.lower():
                color = (50, 150, 50)  # Green for SEO
            else:
                color = (50, 50, 200)  # Blue for Packages

            # Create a colored image
            img = Image.new('RGB', (400, 250), color=color)
            draw = ImageDraw.Draw(img)

            # Add a white border
            draw.rectangle([10, 10, 390, 240], outline=(255, 255, 255), width=5)

            # Save the image
            filepath = os.path.join(app.config['PORTFOLIO_FOLDER'], filename)
            img.save(filepath, 'JPEG')
            print(f"Created sample image on-demand: {filepath}")

            return send_from_directory(app.config['PORTFOLIO_FOLDER'], filename)
        except Exception as e:
            print(f"Error creating sample image: {e}")
            return "Image not found", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
