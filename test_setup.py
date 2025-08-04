#!/usr/bin/env python3
"""
AudioEnhance Pro - Setup Test Script
"""

import sys
import importlib
from pathlib import Path

def test_imports():
    """Test if all required packages can be imported"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'torch',
        'torchaudio',
        'librosa',
        'soundfile',
        'transformers',
        'noisereduce',
        'moviepy',
        'sqlalchemy',
        'pydantic'
    ]
    
    print("🔍 Testing package imports...")
    failed_imports = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package}")
        except ImportError as e:
            print(f"❌ {package}: {e}")
            failed_imports.append(package)
    
    return failed_imports

def test_directories():
    """Test if required directories exist"""
    print("\n📁 Testing directory structure...")
    required_dirs = ['uploads', 'processed', 'temp', 'models']
    
    for directory in required_dirs:
        path = Path(directory)
        if path.exists():
            print(f"✅ {directory}/")
        else:
            print(f"❌ {directory}/ (will be created)")
            path.mkdir(exist_ok=True)

def test_models():
    """Test if AI models can be loaded"""
    print("\n🤖 Testing AI model loading...")
    
    try:
        from transformers import AutoProcessor, AutoModel
        print("✅ Transformers library working")
        
        # Test Wav2Vec2 model loading (this will download the model)
        print("📥 Testing Wav2Vec2 model...")
        model_name = "facebook/wav2vec2-base-960h"
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        print("✅ Wav2Vec2 model loaded successfully")
        
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        return False
    
    return True

def test_audio_processing():
    """Test basic audio processing capabilities"""
    print("\n🎵 Testing audio processing...")
    
    try:
        import numpy as np
        import librosa
        import soundfile as sf
        
        # Create a simple test audio
        sample_rate = 16000
        duration = 1.0  # 1 second
        t = np.linspace(0, duration, int(sample_rate * duration))
        test_audio = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        
        # Test librosa
        librosa.util.fix_length(test_audio, size=len(test_audio))
        print("✅ Librosa working")
        
        # Test soundfile
        test_file = "test_audio.wav"
        sf.write(test_file, test_audio, sample_rate)
        loaded_audio, sr = sf.read(test_file)
        Path(test_file).unlink()  # Clean up
        print("✅ Soundfile working")
        
    except Exception as e:
        print(f"❌ Audio processing test failed: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    print("🎵 AudioEnhance Pro - Setup Test")
    print("=" * 40)
    
    # Test Python version
    print(f"🐍 Python version: {sys.version}")
    
    # Test imports
    failed_imports = test_imports()
    
    # Test directories
    test_directories()
    
    # Test models (only if imports succeeded)
    if not failed_imports:
        test_models()
        test_audio_processing()
    
    # Summary
    print("\n" + "=" * 40)
    if failed_imports:
        print(f"❌ Setup incomplete. Failed imports: {', '.join(failed_imports)}")
        print("💡 Run: pip install -r requirements.txt")
        return False
    else:
        print("✅ Setup test completed successfully!")
        print("🚀 You can now run: python run.py")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)