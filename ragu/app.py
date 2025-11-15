from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import pandas as pd
import os
import hashlib
from threading import Lock

app = Flask(__name__, static_folder='static', template_folder='templates')

# ===== CORS CONFIGURATION =====
CORS(app)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "DELETE", "PUT", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Excel file paths
REVIEWS_FILE = 'data/reviews.xlsx'
ADMINS_FILE = 'data/admins.xlsx'

# Thread-safe file operations
file_lock = Lock()

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

# ===== EXCEL INITIALIZATION =====
def init_excel_files():
    """Initialize Excel files if they don't exist"""
    try:
        # Initialize Reviews file
        if not os.path.exists(REVIEWS_FILE):
            df_reviews = pd.DataFrame(columns=[
                'id', 'name', 'email', 'phone', 'review', 'rating', 'created_at'
            ])
            df_reviews.to_excel(REVIEWS_FILE, index=False)
            print(f"✓ Created {REVIEWS_FILE}")
        
        # Initialize Admins file
        if not os.path.exists(ADMINS_FILE):
            df_admins = pd.DataFrame(columns=[
                'id', 'username', 'password_hash', 'created_at'
            ])
            # Create default admin
            password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
            df_admins = pd.DataFrame([{
                'id': 1,
                'username': 'admin',
                'password_hash': password_hash,
                'created_at': datetime.utcnow().isoformat()
            }])
            df_admins.to_excel(ADMINS_FILE, index=False)
            print(f"✓ Created {ADMINS_FILE}")
            print("✓ Default admin created - Username: admin, Password: admin123")
            print("⚠ IMPORTANT: Change the default password immediately!")
        
        print("✓ Excel files initialized successfully")
    except Exception as e:
        print(f"✗ Excel initialization error: {e}")

# ===== HELPER FUNCTIONS =====
def read_excel_safe(filepath):
    """Thread-safe Excel reading"""
    with file_lock:
        try:
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return pd.read_excel(filepath)
            else:
                return pd.DataFrame()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return pd.DataFrame()

def write_excel_safe(filepath, df):
    """Thread-safe Excel writing"""
    with file_lock:
        try:
            df.to_excel(filepath, index=False)
            return True
        except Exception as e:
            print(f"Error writing to {filepath}: {e}")
            return False

def get_next_id(df):
    """Get next available ID"""
    if df.empty or 'id' not in df.columns:
        return 1
    return int(df['id'].max()) + 1 if not df['id'].isna().all() else 1

# ===== MAIN ROUTES =====

@app.route('/')
def home():
    """Main API endpoint - returns API info"""
    return jsonify({
        'message': 'AR VELS Manpower Global Consultancy API',
        'version': '2.0',
        'storage': 'Excel',
        'status': 'online ✓',
        'author': 'AR VELS Team',
        'endpoints': {
            'GET /': 'Main API info',
            'GET /api/health': 'Health check',
            'GET /api/reviews': 'Get all reviews',
            'GET /api/reviews?limit=5': 'Get limited reviews',
            'POST /api/reviews': 'Submit a new review',
            'GET /api/reviews/<id>': 'Get specific review',
            'DELETE /api/reviews/<id>': 'Delete a review',
            'GET /api/stats': 'Get statistics',
            'POST /api/admin/login': 'Admin login',
            'GET /api/backup/reviews': 'Download reviews backup'
        }
    })

@app.route('/admin')
def admin():
    """Admin dashboard page"""
    return jsonify({
        'message': 'Admin Dashboard',
        'instruction': 'Open admin.html file in browser',
        'login': 'POST /api/admin/login with username and password'
    })

# ===== HEALTH CHECK =====

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Health check endpoint"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        reviews_exists = os.path.exists(REVIEWS_FILE)
        admins_exists = os.path.exists(ADMINS_FILE)
        
        return jsonify({
            'status': 'healthy ✓',
            'message': 'API is running correctly',
            'storage': 'Excel',
            'files': {
                'reviews': reviews_exists,
                'admins': admins_exists
            },
            'timestamp': datetime.utcnow().isoformat(),
            'cors': 'enabled ✓'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy ✗',
            'error': str(e)
        }), 500

# ===== REVIEWS ENDPOINTS =====

@app.route('/api/reviews', methods=['GET', 'OPTIONS'])
def get_reviews():
    """Get all reviews with optional limit"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        limit = request.args.get('limit', type=int)
        
        df_reviews = read_excel_safe(REVIEWS_FILE)
        
        if df_reviews.empty:
            return jsonify([])
        
        # Sort by created_at descending (newest first)
        df_reviews['created_at'] = pd.to_datetime(df_reviews['created_at'])
        df_reviews = df_reviews.sort_values('created_at', ascending=False)
        
        if limit:
            df_reviews = df_reviews.head(limit)
        
        # Convert to list of dictionaries
        reviews = df_reviews.to_dict('records')
        
        # Format datetime as ISO string
        for review in reviews:
            if isinstance(review['created_at'], pd.Timestamp):
                review['created_at'] = review['created_at'].isoformat()
            review['id'] = int(review['id'])
            review['rating'] = int(review['rating'])
        
        return jsonify(reviews)
    except Exception as e:
        print(f"Get reviews error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reviews/<int:review_id>', methods=['GET', 'OPTIONS'])
def get_review(review_id):
    """Get a specific review by ID"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        df_reviews = read_excel_safe(REVIEWS_FILE)
        review = df_reviews[df_reviews['id'] == review_id]
        
        if review.empty:
            return jsonify({'error': 'Review not found'}), 404
        
        review_dict = review.iloc[0].to_dict()
        if isinstance(review_dict['created_at'], pd.Timestamp):
            review_dict['created_at'] = review_dict['created_at'].isoformat()
        review_dict['id'] = int(review_dict['id'])
        review_dict['rating'] = int(review_dict['rating'])
        
        return jsonify(review_dict)
    except Exception as e:
        print(f"Get review error: {e}")
        return jsonify({'error': 'Review not found'}), 404

@app.route('/api/reviews', methods=['POST', 'OPTIONS'])
def create_review():
    """Submit a new review"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        print(f"📝 Received review data: {data}")
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'review', 'rating']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Validate rating
        try:
            rating = int(data['rating'])
            if rating < 1 or rating > 5:
                return jsonify({
                    'success': False,
                    'error': 'Rating must be between 1 and 5'
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': 'Rating must be a number between 1 and 5'
            }), 400
        
        # Read existing reviews
        df_reviews = read_excel_safe(REVIEWS_FILE)
        
        # Create new review
        new_id = get_next_id(df_reviews)
        new_review = {
            'id': new_id,
            'name': data['name'].strip(),
            'email': data['email'].strip(),
            'phone': data['phone'].strip(),
            'review': data['review'].strip(),
            'rating': rating,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Append new review
        df_reviews = pd.concat([df_reviews, pd.DataFrame([new_review])], ignore_index=True)
        
        # Save to Excel
        if write_excel_safe(REVIEWS_FILE, df_reviews):
            print(f"✅ Review created successfully: ID {new_id}")
            return jsonify({
                'success': True,
                'message': 'Review submitted successfully ✓',
                'id': new_id,
                'review': new_review
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save review'
            }), 500
    except Exception as e:
        print(f"❌ Create review error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/reviews/<int:review_id>', methods=['DELETE', 'OPTIONS'])
def delete_review(review_id):
    """Delete a review by ID"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        df_reviews = read_excel_safe(REVIEWS_FILE)
        
        if df_reviews[df_reviews['id'] == review_id].empty:
            return jsonify({
                'success': False,
                'error': 'Review not found'
            }), 404
        
        # Remove the review
        df_reviews = df_reviews[df_reviews['id'] != review_id]
        
        # Save to Excel
        if write_excel_safe(REVIEWS_FILE, df_reviews):
            print(f"✅ Review {review_id} deleted successfully")
            return jsonify({
                'success': True,
                'message': 'Review deleted successfully ✓'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete review'
            }), 500
    except Exception as e:
        print(f"❌ Delete review error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== STATISTICS ENDPOINT =====

@app.route('/api/stats', methods=['GET', 'OPTIONS'])
def get_stats():
    """Get statistics about reviews"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        df_reviews = read_excel_safe(REVIEWS_FILE)
        
        if df_reviews.empty:
            return jsonify({
                'total_reviews': 0,
                'average_rating': 0,
                'rating_distribution': {
                    '1_star': 0,
                    '2_star': 0,
                    '3_star': 0,
                    '4_star': 0,
                    '5_star': 0
                },
                'today_reviews': 0
            })
        
        total_reviews = len(df_reviews)
        avg_rating = df_reviews['rating'].mean()
        
        rating_distribution = {}
        for i in range(1, 6):
            count = len(df_reviews[df_reviews['rating'] == i])
            rating_distribution[f'{i}_star'] = count
        
        # Today's reviews
        df_reviews['created_at'] = pd.to_datetime(df_reviews['created_at'])
        today = datetime.utcnow().date()
        today_reviews = len(df_reviews[df_reviews['created_at'].dt.date == today])
        
        return jsonify({
            'total_reviews': total_reviews,
            'average_rating': round(avg_rating, 2),
            'rating_distribution': rating_distribution,
            'today_reviews': today_reviews
        })
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== ADMIN ENDPOINTS =====

@app.route('/api/admin/login', methods=['POST', 'OPTIONS'])
def admin_login():
    """Admin login endpoint"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Username and password required'
            }), 400
        
        df_admins = read_excel_safe(ADMINS_FILE)
        admin = df_admins[df_admins['username'] == username]
        
        if not admin.empty:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if admin.iloc[0]['password_hash'] == password_hash:
                return jsonify({
                    'success': True,
                    'message': 'Login successful ✓',
                    'username': username
                })
        
        return jsonify({
            'success': False,
            'message': 'Invalid credentials'
        }), 401
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/change-password', methods=['POST', 'OPTIONS'])
def change_password():
    """Change admin password"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        username = data.get('username')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not all([username, old_password, new_password]):
            return jsonify({
                'success': False,
                'message': 'All fields are required'
            }), 400
        
        df_admins = read_excel_safe(ADMINS_FILE)
        admin_idx = df_admins[df_admins['username'] == username].index
        
        if not admin_idx.empty:
            old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            if df_admins.loc[admin_idx[0], 'password_hash'] == old_hash:
                new_hash = hashlib.sha256(new_password.encode()).hexdigest()
                df_admins.loc[admin_idx[0], 'password_hash'] = new_hash
                
                if write_excel_safe(ADMINS_FILE, df_admins):
                    print(f"✅ Password changed for admin: {username}")
                    return jsonify({
                        'success': True,
                        'message': 'Password changed successfully ✓'
                    })
        
        return jsonify({
            'success': False,
            'message': 'Invalid credentials'
        }), 401
    except Exception as e:
        print(f"❌ Password change error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===== BACKUP ENDPOINT =====

@app.route('/api/backup/reviews', methods=['GET'])
def backup_reviews():
    """Download reviews Excel file as backup"""
    try:
        return send_from_directory('data', 'reviews.xlsx', as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Resource not found',
        'status': 404
    }), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'status': 500
    }), 500

# ===== STARTUP =====

# Initialize Excel files on startup
init_excel_files()

if __name__ == '__main__':
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    print("\n" + "="*60)
    print("🚀 AR VELS Manpower Global Consultancy - API Server")
    print("="*60)
    print(f"📁 Storage: Excel Files")
    print(f"🔌 Port: {port}")
    print(f"🌍 Environment: {'Production (Render)' if os.environ.get('RENDER') else 'Development (Local)'}")
    print(f"✅ CORS: Enabled for all origins")
    print("="*60)
    print("\n✓ API ready! Visit: http://localhost:{}/api/health\n".format(port))
    print("="*60 + "\n")
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)
