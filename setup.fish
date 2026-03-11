#!/usr/bin/env fish

echo "Creating python virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate.fish

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Environment initialized successfully!"
echo "To activate manually, run: source venv/bin/activate.fish"
echo "To run the app, run: uvicorn main:app --reload"
