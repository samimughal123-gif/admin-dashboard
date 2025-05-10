# Agency Admin Panel

This is a web-based admin panel for the Agency App. It allows administrators to manage orders, view customer information, and receive notifications for new orders.

## Features

- Secure admin login
- Dashboard with order statistics
- Order management (view, update status)
- Real-time notifications for new orders
- Responsive design for desktop and mobile

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

1. Navigate to the admin_panel directory:
   ```
   cd admin_panel
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

### Running the Admin Panel

1. Make sure the virtual environment is activated (if you created one)

2. Run the Flask application:
   ```
   python app.py
   ```

3. Open a web browser and navigate to:
   ```
   http://localhost:5000
   ```

4. Log in with the admin credentials:
   - Username: admin
   - Password: admin

### Security Notes

- For production use, change the default admin password in the database
- Update the secret key in app.py for production
- Consider using HTTPS for secure communication

## Integration with the Agency App

The admin panel connects to the same database as the Agency App, so any orders placed through the mobile app will automatically appear in the admin panel.

## Notifications

The admin panel checks for new orders every 30 seconds and displays a notification badge when new orders are received. This allows administrators to stay informed about new business without constantly refreshing the page.
