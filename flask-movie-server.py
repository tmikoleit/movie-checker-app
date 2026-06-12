#!/usr/bin/env python3
"""
Movie Blu-ray comparison web server.
Upload a photo → get instant "you own / don't own" results.
Accessible only via Tailscale.
"""

import os
import subprocess
import base64
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from anthropic import Anthropic

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

client = Anthropic()

# Set up file logging for auto-check operations
LOG_DIR = Path('/tmp')
LOG_FILE = LOG_DIR / 'movie-checker-wishlist.log'

def log_event(message):
    """Log event with timestamp to file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_message + '\n')
    except Exception as e:
        print(f"Failed to write log: {e}")
    print(log_message)

def load_owned_movies() -> set:
    """Load owned movies from NAS via SSH."""
    try:
        result = subprocess.run(
            ['ssh', 'nas', 'cat "/volume1/Obsidian/Data Hoarding/Movie Inventory.md"'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print(f"SSH error: {result.stderr}")
            return set()

        owned = set()
        in_list = False
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line == "## All Owned Movies":
                in_list = True
                continue
            if in_list and line.startswith("- "):
                movie = line[2:].strip()
                owned.add(movie.lower())

        print(f"Loaded {len(owned)} movies from NAS")
        return owned
    except Exception as e:
        print(f"Error loading inventory: {e}")
        return set()

def extract_titles_from_image(image_path: str) -> list:
    """Use Claude's vision to extract movie titles from image."""
    try:
        with open(image_path, 'rb') as img_file:
            image_data = base64.standard_b64encode(img_file.read()).decode('utf-8')

        ext = Path(image_path).suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')

        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": """Please read all the Blu-ray or DVD titles visible in this image.
Extract ONLY the movie titles you can see on the spines or cases.
Return them as a simple list, one title per line.
If you can't read a title clearly, skip it.
Include the year if visible, but it's optional."""
                        }
                    ]
                }
            ]
        )

        titles = []
        for line in response.content[0].text.split('\n'):
            line = str(line).strip()  # Ensure string
            # Skip Claude's explanatory text and empty lines
            if not line or line.lower().startswith(('here', 'extract', 'please', 'return', 'format')):
                continue
            # Skip lines that are just numbers
            if line and line[0].isdigit():
                continue
            # Extract title
            title = line.lstrip('0123456789.- ').strip()
            if title and len(title) > 2 and isinstance(title, str):
                titles.append(title)

        print(f"Extracted {len(titles)} titles from image")
        return titles
    except Exception as e:
        print(f"Error extracting titles: {e}")
        raise

def fuzzy_match(extracted_title: str, owned_movies: set):
    """Find close match in owned movies. Returns (match_type, matched_title, confidence)."""
    from difflib import SequenceMatcher
    import re

    def normalize(s):
        """Normalize title: remove punctuation, subtitles, years."""
        s = s.lower()
        # Remove anything after a colon (subtitles)
        s = s.split(':')[0].strip()
        # Remove years in parentheses
        s = re.sub(r'\s*\(\d{4}\)\s*', ' ', s)
        # Remove punctuation
        s = re.sub(r'[^a-z0-9\s]', '', s)
        # Remove extra spaces
        s = ' '.join(s.split())
        return s

    extracted_norm = normalize(extracted_title)

    # Try exact match first
    if extracted_norm in [normalize(m) for m in owned_movies]:
        return ('confirmed', extracted_title, 1.0)

    # Fuzzy match
    best_match = None
    best_ratio = 0

    for owned in owned_movies:
        owned_norm = normalize(owned)
        ratio = SequenceMatcher(None, extracted_norm, owned_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = owned

    # Categorize by confidence
    if best_ratio >= 0.85:
        return ('confirmed', best_match, best_ratio)
    elif best_ratio >= 0.50:
        return ('likely', best_match, best_ratio)
    else:
        return ('no_match', None, best_ratio)

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html')

@app.route('/api/compare-text', methods=['POST'])
def compare_text():
    """Accept text titles, compare against inventory."""
    try:
        data = request.get_json()
        if not data or 'titles' not in data:
            return jsonify({'error': 'No titles provided'}), 400

        titles = data['titles']
        if not isinstance(titles, list) or len(titles) == 0:
            return jsonify({'error': 'Titles must be a non-empty list'}), 400

        # Load inventory
        owned_movies = load_owned_movies()
        if not owned_movies:
            return jsonify({'error': 'Could not load movie inventory from NAS'}), 500

        confirmed = []
        likely = []
        no_match = []

        for title in titles:
            title = str(title).strip()
            if not title:
                continue

            match_type, matched_title, confidence = fuzzy_match(title, owned_movies)
            confidence_pct = round(confidence * 100)

            if match_type == 'confirmed':
                confirmed.append({
                    'extracted': title,
                    'matched': matched_title,
                    'confidence': confidence_pct
                })
            elif match_type == 'likely':
                likely.append({
                    'extracted': title,
                    'matched': matched_title,
                    'confidence': confidence_pct
                })
            else:
                no_match.append({
                    'extracted': title,
                    'matched': str(matched_title).strip() if matched_title else None,
                    'confidence': confidence_pct
                })

        response_data = {
            'success': True,
            'confirmed': confirmed,
            'likely': likely,
            'no_match': no_match,
            'total_extracted': len(titles),
            'confirmed_count': len(confirmed),
            'likely_count': len(likely),
            'no_match_count': len(no_match)
        }

        return jsonify(response_data)

    except Exception as e:
        print(f"ERROR in /api/compare-text: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/compare', methods=['POST'])
def compare():
    """Accept photo, compare against inventory."""
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'No photo uploaded'}), 400

        file = request.files['photo']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Save temp file
        with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        try:
            # Extract titles from image
            extracted = extract_titles_from_image(temp_path)
            if not extracted:
                return jsonify({'error': 'Could not extract any titles from image'}), 400

            # Load inventory
            owned_movies = load_owned_movies()
            if not owned_movies:
                return jsonify({'error': 'Could not load movie inventory from NAS'}), 500

            # Compare with three-tier matching
            confirmed = []
            likely = []
            no_match = []

            for title in extracted:
                title = str(title).strip()  # Ensure title is a string
                match_type, matched_title, confidence = fuzzy_match(title, owned_movies)
                confidence_pct = round(confidence * 100)

                if match_type == 'confirmed':
                    confirmed.append({
                        'extracted': title,
                        'matched': matched_title,
                        'confidence': confidence_pct
                    })
                elif match_type == 'likely':
                    likely.append({
                        'extracted': title,
                        'matched': matched_title,
                        'confidence': confidence_pct
                    })
                else:
                    # No match - include closest match if found, even if below threshold
                    no_match.append({
                        'extracted': title,
                        'matched': str(matched_title).strip() if matched_title else None,
                        'confidence': confidence_pct
                    })

            # Sort no_match by extracted title
            no_match_sorted = sorted(no_match, key=lambda x: x['extracted'] if isinstance(x, dict) else x)

            response_data = {
                'success': True,
                'confirmed': confirmed,
                'likely': likely,
                'no_match': no_match_sorted,
                'total_extracted': len(extracted),
                'confirmed_count': len(confirmed),
                'likely_count': len(likely),
                'no_match_count': len(no_match)
            }

            print(f"SUCCESS: {len(confirmed)} confirmed, {len(likely)} likely, {len(no_match)} no_match")
            print(f"no_match data: {no_match_sorted}")
            return jsonify(response_data)

        finally:
            os.unlink(temp_path)

    except Exception as e:
        print(f"ERROR in /api/compare: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/save-wishlist', methods=['POST'])
def save_wishlist():
    """Save wishlist items to Obsidian vault."""
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': 'No items provided'}), 400

        items = data['items']
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({'error': 'Items must be a non-empty list'}), 400

        # Get existing wishlist content
        wishlist_path = '/volume1/Obsidian/Data Hoarding/Wishlist.md'
        try:
            result = subprocess.run(
                ['ssh', 'nas', f'cat "{wishlist_path}"'],
                capture_output=True,
                text=True,
                timeout=10
            )
            existing_content = result.stdout if result.returncode == 0 else None
        except:
            existing_content = None

        # Parse existing items to avoid duplicates
        existing_titles = set()
        if existing_content:
            for line in existing_content.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    # Extract title (remove the format tag at end)
                    title = line[2:].rsplit(' (', 1)[0].strip()
                    existing_titles.add(title.lower())

        # Filter out duplicates
        new_items = [item for item in items if item['title'].lower() not in existing_titles]

        if not new_items:
            return jsonify({'success': True, 'message': 'All movies already in wishlist'}), 200

        # Format new items
        new_lines = []
        for item in new_items:
            format_tag = '4K' if item.get('is4k') else 'Blu-ray'
            new_lines.append(f"- {item['title']} ({format_tag})")

        new_content = '\n'.join(new_lines)

        # If file doesn't exist, create with header first
        if not existing_content:
            result = subprocess.run(
                ['ssh', 'nas', f'cat > "{wishlist_path}"'],
                input="# Wishlist\n",
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                print(f"SSH write error: {result.stderr}")
                return jsonify({'error': f'Failed to create wishlist: {result.stderr}'}), 500

        # Always append new items
        result = subprocess.run(
            ['ssh', 'nas', f'cat >> "{wishlist_path}"'],
            input='\n' + new_content,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            print(f"SSH write error: {result.stderr}")
            return jsonify({'error': f'Failed to write to Obsidian: {result.stderr}'}), 500

        return jsonify({'success': True, 'message': f'Added {len(new_items)} movies to wishlist'}), 200

    except Exception as e:
        print(f"ERROR in /api/save-wishlist: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/auto-check-wishlist', methods=['POST'])
def auto_check_wishlist():
    """Check wishlist against owned movies, remove 95%+ matches automatically."""
    try:
        log_event("=== Starting wishlist auto-check ===")

        # Load owned movies
        owned_movies = load_owned_movies()
        if not owned_movies:
            log_event("ERROR: Could not load movie inventory from NAS")
            return jsonify({'error': 'Could not load movie inventory from NAS'}), 500

        log_event(f"Loaded {len(owned_movies)} movies from inventory")

        # Load wishlist
        wishlist_path = '/volume1/Obsidian/Data Hoarding/Wishlist.md'
        try:
            result = subprocess.run(
                ['ssh', 'nas', f'cat "{wishlist_path}"'],
                capture_output=True,
                text=True,
                timeout=10
            )
            wishlist_content = result.stdout if result.returncode == 0 else None
        except Exception as e:
            log_event(f"ERROR: Failed to read wishlist: {e}")
            wishlist_content = None

        if not wishlist_content:
            log_event("Wishlist not found or empty")
            return jsonify({'message': 'Wishlist not found or empty', 'removed': []}), 200

        # Parse wishlist items
        wishlist_items = []
        for line in wishlist_content.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                title = line[2:].rsplit(' (', 1)[0].strip()
                wishlist_items.append(title)

        log_event(f"Checking {len(wishlist_items)} wishlist items for 95%+ matches")

        # Check each wishlist item for 95%+ matches
        removed_items = []
        kept_items = []

        for item in wishlist_items:
            match_type, matched_title, confidence = fuzzy_match(item, owned_movies)
            confidence_pct = round(confidence * 100)

            if match_type == 'confirmed' and confidence >= 0.95:
                log_event(f"REMOVE: '{item}' → '{matched_title}' ({confidence_pct}%)")
                removed_items.append({
                    'title': item,
                    'matched': matched_title,
                    'confidence': confidence_pct
                })
            else:
                kept_items.append(item)

        if not removed_items:
            log_event(f"No 95%+ matches found. All {len(wishlist_items)} items kept.")
            return jsonify({
                'message': 'No 95%+ matches found',
                'removed': [],
                'checked': len(wishlist_items)
            }), 200

        # Rewrite wishlist without removed items
        new_lines = ['# Wishlist']
        for item in kept_items:
            new_lines.append(f"- {item} (Blu-ray)")

        new_content = '\n'.join(new_lines) + '\n'

        # Write updated wishlist back
        result = subprocess.run(
            ['ssh', 'nas', f'cat > "{wishlist_path}"'],
            input=new_content,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            log_event(f"ERROR: SSH write failed: {result.stderr}")
            return jsonify({'error': f'Failed to update wishlist: {result.stderr}'}), 500

        log_event(f"SUCCESS: Removed {len(removed_items)} movies. {len(kept_items)} items remain in wishlist.")

        return jsonify({
            'success': True,
            'message': f'Removed {len(removed_items)} movies from wishlist',
            'removed': removed_items,
            'checked': len(wishlist_items)
        }), 200

    except Exception as e:
        log_event(f"ERROR: Unexpected error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/health')
def health():
    """Health check."""
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
