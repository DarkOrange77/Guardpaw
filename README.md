# 🐾 GuardPaw: Multimodal Animal Rescue Scam Detector

GuardPaw is an AI-powered tool designed to detect potential scams in animal rescue fundraisers. It analyzes text descriptions, images, and fundraiser links to assess the risk level of fraudulent activities, helping protect donors from falling victim to fake rescue operations.

## 🚀 Features

- **Multimodal Analysis**: Processes text, images, and URLs simultaneously
- **Risk Assessment**: Provides HIGH/MEDIUM/LOW risk levels with confidence scores
- **Pattern Recognition**: Uses a knowledge base of 16 scam patterns and legit indicators
- **Vision Analysis**: Detects image manipulation, watermarks, and staging using advanced AI
- **Link Inspection**: Performs multi-layer domain and content analysis
- **Web Dashboard**: User-friendly interface for easy analysis
- **API Integration**: RESTful API for programmatic access

## 📋 Requirements

- Python 3.8+
- Internet connection for link analysis and vision processing
- Hugging Face API access (for vision analysis)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/guardpaw.git
   cd guardpaw
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the root directory with necessary API keys:
   ```
   HUGGINGFACE_API_KEY=your_huggingface_api_key
   GOOGLE_API_KEY=your_google_api_key
   SERPAPI_API_KEY=your_serpapi_api_key
   ```

## 🎯 Usage

### Web Dashboard

1. **Start the application:**
   ```bash
   # On Windows
   start_dashboard.bat
   
   # Or manually:
   python app/api.py
   ```

2. **Open your browser** and navigate to `http://localhost:5000`

3. **Analyze content:**
   - Enter suspicious text description
   - Upload an image (optional)
   - Provide a fundraiser URL (optional)
   - Click "Analyze" to get risk assessment

### API Usage

```python
from app.pipeline import GuardPawPipeline

pipeline = GuardPawPipeline()
result = pipeline.analyze_submission(
    user_text="Emergency puppy rescue, $3k surgery needed...",
    image_path="/path/to/image.jpg",
    link_url="https://suspicious-fundraiser.com"
)

print(f"Risk Level: {result['risk_level']}")
print(f"Confidence: {result['confidence']}")
print(f"Explanation: {result['explanation']}")
```

### Demo

Run the included demo to see GuardPaw in action:

```bash
python tests/demo.py
```

This demonstrates text-only vs. multimodal analysis on sample scam content.

## 🏗️ Architecture

GuardPaw consists of three main analysis modules:

1. **Text Engine** (`engine.py`): Semantic search against scam/legit pattern knowledge base using RAG
2. **Vision Analyzer** (`vision.py`): AI-powered image forensics using Qwen2-VL-7B
3. **Link Analyzer** (`link_analysis.py`): Multi-layer URL and content inspection

The `pipeline.py` orchestrates all modules and combines signals for final risk assessment.

## 📁 Project Structure

```
GuardPaw/
├── app/
│   ├── api.py              # Flask API server
│   ├── pipeline.py         # Main analysis orchestrator
│   ├── engine.py           # Text analysis engine
│   ├── vision.py           # Image analysis module
│   ├── link_analysis.py    # URL analysis module
│   └── main.py             # Entry point (currently empty)
├── data/
│   ├── scam_patterns/      # 10 scam pattern documents
│   ├── legit_indicators/   # 5 legitimacy indicators
│   └── case_summaries/     # Real case examples
├── Frontend/
│   └── Dashboard.html      # Web interface
├── rag/
│   └── vector_store/       # FAISS vector database
├── tests/
│   ├── demo.py             # Demonstration script
│   └── sample_*.txt        # Test data
├── requirements.txt        # Python dependencies
├── start_dashboard.bat     # Windows launcher
└── README.md               
```

## 🔍 How It Works

1. **Input Processing**: Accepts any combination of text, image, and URL
2. **Signal Extraction**: Each module analyzes its input type independently
3. **Pattern Matching**: Compares against knowledge base of known scam patterns
4. **Risk Scoring**: Combines signals with weighted multipliers
5. **Confidence Calculation**: Determines reliability based on signal agreement
6. **Explanation Generation**: Provides human-readable assessment

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

GuardPaw is a tool to assist in scam detection but should not be relied upon as the sole means of verification. Always perform additional independent checks before making donations.

## 📞 Support

For questions or issues, please open an issue on GitHub or contact the maintainers.

---

**Protect animals and donors from scams with GuardPaw!** 🐶🐱
