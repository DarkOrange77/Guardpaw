"""
GuardPaw Flask API - Connects Dashboard to Pipeline
Provides /analyze endpoint for the frontend to call
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
import sys
import base64
import tempfile
import os
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import GuardPawPipeline

app = Flask(__name__, static_folder=str(Path(__file__).parent.parent / 'Frontend'), static_url_path='/')
CORS(app)

# Initialize pipeline
pipeline = GuardPawPipeline()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle_base64_image(image_data: str) -> str:
    """
    Convert base64 data URL to a temporary file path.
    Returns the file path if successful, otherwise returns the original data.
    
    Handles:
    - data:image/png;base64,... 
    - data:image/jpeg;base64,...
    - raw base64 strings
    """
    if not image_data or not isinstance(image_data, str):
        return image_data
    
    try:
        # Check if it's a data URL
        if image_data.startswith('data:image'):
            # Extract base64 part
            header, encoded = image_data.split(',', 1)
            img_data = base64.b64decode(encoded)
            
            # Determine image format
            img_format = 'png'
            if 'jpeg' in header or 'jpg' in header:
                img_format = 'jpg'
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f'.{img_format}',
                delete=False,
                dir=tempfile.gettempdir()
            )
            temp_file.write(img_data)
            temp_file.close()
            
            logger.info(f"Converted base64 image to temporary file: {temp_file.name}")
            return temp_file.name
        
        # If it's raw base64 (no header), try to decode it
        elif len(image_data) > 100 and not image_data.startswith('/'):
            try:
                img_data = base64.b64decode(image_data)
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.jpg',
                    delete=False,
                    dir=tempfile.gettempdir()
                )
                temp_file.write(img_data)
                temp_file.close()
                logger.info(f"Converted raw base64 to temporary file: {temp_file.name}")
                return temp_file.name
            except Exception:
                pass
        
        # If it's a regular file path, return as-is
        return image_data
        
    except Exception as e:
        logger.warning(f"Could not convert base64 image: {e}")
        return image_data



@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return app.send_static_file('Dashboard.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analyze submission endpoint
    
    Request JSON:
    {
        "user_text": "string or null",
        "link_url": "string or null",
        "image_path": "string (file path or base64 data URL) or null"
    }
    
    Response JSON:
    {
        "risk_level": "HIGH|MEDIUM|LOW",
        "risk_score": number,
        "confidence": "High|Moderate|Low",
        "matched_patterns": [...],
        "explanation": "detailed explanation text",
        "recommendation": "actionable recommendation",
        "signals": {...},
        "input_summary": {...}
    }
    """
    try:
        data = request.get_json()
        
        user_text = data.get('user_text')
        link_url = data.get('link_url')
        image_path = data.get('image_path')
        
        # Handle base64 images from frontend
        if image_path:
            image_path = handle_base64_image(image_path)
            logger.info(f"Processed image_path: {image_path[:50] if len(image_path) > 50 else image_path}")
        
        # Validate input
        if not user_text and not link_url and not image_path:
            return jsonify({'error': 'No input provided'}), 400
        
        # Run analysis
        logger.info(f"Analyzing submission: text={bool(user_text)}, link={bool(link_url)}, image={bool(image_path)}")
        result = pipeline.analyze_submission(user_text, image_path, link_url)
        
        # Format response for frontend
        response = {
            'risk_level': result['risk_level'],
            'risk_score': result['risk_score'],
            'confidence': result['confidence'],
            'matched_patterns': [
                {
                    'name': p['name'].replace('_', ' ').title(),
                    'type': 'scam' if 'scam' in p.get('category', '').lower() else ('legit' if 'legit' in p.get('category', '').lower() else 'case'),
                    'source': p['source'],
                    'weight': p['weight'],
                    'category': p.get('category', '')
                }
                for p in result['matched_patterns']
            ],
            'explanation': result['explanation'],
            'recommendation': result['recommendation'],
            'signals': result['signals'],
            'input_summary': result['input_summary']
        }
        
        logger.info(f"Analysis complete: {result['risk_level']} ({result['risk_score']})")
        logger.info(f"Response keys: {response.keys()}")
        logger.info(f"Risk score sent: {response['risk_score']}")
        logger.info(f"Risk level sent: {response['risk_level']}")
        logger.info(f"Patterns count: {len(response['matched_patterns'])}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'type': 'error'}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'GuardPaw API'}), 200


@app.route('/info', methods=['GET'])
def info():
    """API info endpoint"""
    return jsonify({
        'name': 'GuardPaw Scam Detection API',
        'version': '1.0.0',
        'description': 'Multimodal animal rescue scam detector',
        'endpoints': {
            '/analyze': 'POST - Analyze submission (text, link, image)',
            '/health': 'GET - Health check',
            '/info': 'GET - API info'
        }
    }), 200


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🛡️  GUARDPAW - ANIMAL RESCUE SCAM DETECTION DASHBOARD")
    print("=" * 70)
    print("\n✅ GuardPaw Pipeline Ready")
    print("✅ Flask API Starting...\n")
    print("📊 Dashboard:  http://localhost:5000")
    print("🔌 API:        http://localhost:5000/analyze")
    print("💻 Health:     http://localhost:5000/health")
    print("\n" + "=" * 70)
    print("Open http://localhost:5000 in your browser")
    print("=" * 70 + "\n")
    
    # Run Flask server
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
        sys.exit(0)
