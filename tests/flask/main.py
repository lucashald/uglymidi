#!/usr/bin/env python3
"""
Flask web application for ugly_midi converter.

This Flask app provides web endpoints for all the main ugly_midi functions,
allowing users to convert between VexFlow JSON and MIDI through a web interface.
"""

from flask import Flask, request, jsonify, render_template, send_file, abort
import ugly_midi
import json
import tempfile
import os
from pathlib import Path
import traceback
from werkzeug.utils import secure_filename
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Allowed file extensions
ALLOWED_JSON_EXTENSIONS = {'json'}
ALLOWED_MIDI_EXTENSIONS = {'mid', 'midi'}
ALLOWED_EXTENSIONS = ALLOWED_JSON_EXTENSIONS | ALLOWED_MIDI_EXTENSIONS


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def handle_error(error_message, status_code=400):
    """Return standardized error response."""
    return jsonify({'success': False, 'error': error_message}), status_code


@app.route('/')
def index():
    """Main page with interface for testing ugly_midi functions."""
    return render_template('index.html')


@app.route('/api/json-to-midi', methods=['POST'])
def json_to_midi():
    """Convert VexFlow JSON to MIDI and return as downloadable file."""
    try:
        # Get JSON data from request
        if request.is_json:
            json_data = request.get_json()
        else:
            return handle_error("Request must contain JSON data")

        if not json_data:
            return handle_error("No JSON data provided")

        # Get optional tempo override
        tempo_override = request.args.get('tempo', type=int)

        # Convert JSON to MIDI
        midi_data = ugly_midi.json_to_midi(json_data, tempo_override)

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.mid', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Save MIDI data
        ugly_midi.save_midi(midi_data, temp_path)

        # Get instrument name for filename
        instrument = json_data.get('instrument', 'song')
        filename = f"{instrument}.mid"

        return send_file(temp_path,
                         as_attachment=True,
                         download_name=filename,
                         mimetype='audio/midi')

    except Exception as e:
        return handle_error(f"Error converting JSON to MIDI: {str(e)}")


@app.route('/api/midi-to-json', methods=['POST'])
def midi_to_json():
    """Convert uploaded MIDI file to VexFlow JSON."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return handle_error("No file uploaded")

        file = request.files['file']
        if file.filename == '':
            return handle_error("No file selected")

        if not allowed_file(file.filename, ALLOWED_MIDI_EXTENSIONS):
            return handle_error(
                "Invalid file type. Please upload a .mid or .midi file")

        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)

        try:
            # Get optional quantization parameter
            quantize = request.form.get('quantize', 0.25, type=float)

            # Convert MIDI to JSON
            json_data = ugly_midi.midi_to_json(temp_path, quantize)

            return jsonify({
                'success': True,
                'json_data': json_data,
                'filename': filename
            })

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        return handle_error(f"Error converting MIDI to JSON: {str(e)}")


@app.route('/api/create-ensemble', methods=['POST'])
def create_ensemble():
    """Create multi-instrument MIDI from multiple JSON objects."""
    try:
        # Get array of JSON data
        if not request.is_json:
            return handle_error("Request must contain JSON data")

        request_data = request.get_json()

        if not request_data or 'instruments' not in request_data:
            return handle_error("Request must contain 'instruments' array")

        json_list = request_data['instruments']
        if not isinstance(json_list, list) or len(json_list) == 0:
            return handle_error("'instruments' must be a non-empty array")

        # Get optional tempo override
        tempo_override = request_data.get('tempo', type=int)

        # Create ensemble MIDI
        ensemble_midi = ugly_midi.create_ensemble(json_list, tempo_override)

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.mid', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # Save ensemble MIDI
        ugly_midi.save_midi(ensemble_midi, temp_path)

        # Create filename from instrument names
        instruments = [
            json_data.get('instrument', 'unknown') for json_data in json_list
        ]
        filename = f"ensemble_{'_'.join(instruments[:3])}.mid"  # Limit filename length

        return send_file(temp_path,
                         as_attachment=True,
                         download_name=filename,
                         mimetype='audio/midi')

    except Exception as e:
        return handle_error(f"Error creating ensemble: {str(e)}")


@app.route('/api/parse-note', methods=['POST'])
def parse_note():
    """Parse a VexFlow note name and return MIDI note numbers."""
    try:
        data = request.get_json()
        if not data or 'note_name' not in data:
            return handle_error("Request must contain 'note_name'")

        note_name = data['note_name']

        # Use the converter function directly
        from ugly_midi.converter import parse_note_name
        midi_notes = parse_note_name(note_name)

        return jsonify({
            'success': True,
            'note_name': note_name,
            'midi_notes': midi_notes,
            'note_count': len(midi_notes)
        })

    except Exception as e:
        return handle_error(f"Error parsing note: {str(e)}")


@app.route('/api/beats-to-seconds', methods=['POST'])
def beats_to_seconds():
    """Convert beats to seconds given a tempo."""
    try:
        data = request.get_json()
        if not data or 'beats' not in data or 'tempo' not in data:
            return handle_error("Request must contain 'beats' and 'tempo'")

        beats = data['beats']
        tempo = data['tempo']

        # Use the converter function directly
        from ugly_midi.converter import beats_to_seconds as convert_beats
        seconds = convert_beats(beats, tempo)

        return jsonify({
            'success': True,
            'beats': beats,
            'tempo': tempo,
            'seconds': seconds
        })

    except Exception as e:
        return handle_error(f"Error converting beats to seconds: {str(e)}")


@app.route('/api/determine-clef', methods=['POST'])
def determine_clef():
    """Determine appropriate clef for a MIDI note number."""
    try:
        data = request.get_json()
        if not data or 'midi_note' not in data:
            return handle_error("Request must contain 'midi_note'")

        midi_note = data['midi_note']

        # Use the converter function directly
        from ugly_midi.converter import determine_clef as get_clef
        clef = get_clef(midi_note)

        return jsonify({'success': True, 'midi_note': midi_note, 'clef': clef})

    except Exception as e:
        return handle_error(f"Error determining clef: {str(e)}")


@app.route('/api/midi-to-note-name', methods=['POST'])
def midi_to_note_name():
    """Convert MIDI note numbers to VexFlow note name format."""
    try:
        data = request.get_json()
        if not data or 'midi_notes' not in data:
            return handle_error("Request must contain 'midi_notes' array")

        midi_notes = data['midi_notes']
        if not isinstance(midi_notes, list):
            return handle_error("'midi_notes' must be an array")

        # Use the converter function directly
        from ugly_midi.converter import midi_notes_to_name
        note_name = midi_notes_to_name(midi_notes)

        return jsonify({
            'success': True,
            'midi_notes': midi_notes,
            'note_name': note_name,
            'is_chord': len(midi_notes) > 1
        })

    except Exception as e:
        return handle_error(f"Error converting MIDI to note name: {str(e)}")


@app.route('/api/duration-mappings', methods=['GET'])
def duration_mappings():
    """Get all available VexFlow duration mappings."""
    try:
        from ugly_midi.converter import DURATION_TO_BEATS

        return jsonify({
            'success': True,
            'duration_mappings': DURATION_TO_BEATS
        })

    except Exception as e:
        return handle_error(f"Error getting duration mappings: {str(e)}")


@app.route('/api/package-info', methods=['GET'])
def package_info():
    """Get ugly_midi package information."""
    try:
        return jsonify({
            'success': True,
            'package_info': {
                'name': 'ugly_midi',
                'version': ugly_midi.__version__,
                'author': ugly_midi.__author__,
                'email': ugly_midi.__email__,
                'license': ugly_midi.__license__
            }
        })

    except Exception as e:
        return handle_error(f"Error getting package info: {str(e)}")


@app.route('/api/sample-json', methods=['GET'])
def sample_json():
    """Get a sample VexFlow JSON for testing."""
    sample_data = {
        "keySignature":
        "C",
        "tempo":
        120,
        "timeSignature": {
            "numerator": 4,
            "denominator": 4
        },
        "instrument":
        "piano",
        "midiChannel":
        "0",
        "measures": [[{
            "id": "sample-1-1",
            "name": "C4",
            "clef": "treble",
            "duration": "q",
            "measure": 0,
            "isRest": False
        }, {
            "id": "sample-1-2",
            "name": "D4",
            "clef": "treble",
            "duration": "q",
            "measure": 0,
            "isRest": False
        }, {
            "id": "sample-1-3",
            "name": "E4",
            "clef": "treble",
            "duration": "q",
            "measure": 0,
            "isRest": False
        }, {
            "id": "sample-1-4",
            "name": "F4",
            "clef": "treble",
            "duration": "q",
            "measure": 0,
            "isRest": False
        }],
                     [{
                         "id": "sample-2-1",
                         "name": "(C4 E4 G4)",
                         "clef": "treble",
                         "duration": "w",
                         "measure": 1,
                         "isRest": False
                     }]]
    }

    return jsonify({'success': True, 'sample_json': sample_data})


@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return handle_error("File too large. Maximum size is 16MB.", 413)


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return handle_error("Endpoint not found", 404)


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors."""
    return handle_error("Internal server error", 500)


# Cleanup function to remove temporary files
@app.teardown_appcontext
def cleanup_temp_files(error):
    """Clean up any temporary files created during request processing."""
    # This is a basic cleanup - in production, you might want more sophisticated
    # temporary file management
    pass


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)

    print("Starting ugly_midi Flask application...")
    print("Available endpoints:")
    print("  GET  /                     - Main interface")
    print("  POST /api/json-to-midi     - Convert JSON to MIDI")
    print("  POST /api/midi-to-json     - Convert MIDI to JSON")
    print("  POST /api/create-ensemble  - Create multi-instrument MIDI")
    print("  POST /api/parse-note       - Parse VexFlow note names")
    print("  POST /api/beats-to-seconds - Convert beats to seconds")
    print("  POST /api/determine-clef   - Determine clef for MIDI note")
    print("  POST /api/midi-to-note-name - Convert MIDI notes to names")
    print("  GET  /api/duration-mappings - Get duration mappings")
    print("  GET  /api/package-info     - Get package information")
    print("  GET  /api/sample-json      - Get sample JSON data")
    print("\nPackage info:")
    print(f"  ugly_midi version: {ugly_midi.__version__}")
    print(f"  Author: {ugly_midi.__author__}")

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
