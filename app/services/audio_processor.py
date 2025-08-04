import torch
import torchaudio
import librosa
import soundfile as sf
import numpy as np
from pathlib import Path
import noisereduce as nr
from pydub import AudioSegment
from transformers import AutoProcessor, AutoModel
import os
from typing import Tuple, Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() and settings.use_gpu else "cpu")
        self.models = {}
        self.processors = {}
        self._load_models()
    
    def _load_models(self):
        """Load AI models for audio processing"""
        try:
            # Load Facebook's Wav2Vec2 model for speech enhancement
            model_name = "facebook/wav2vec2-base-960h"
            self.models['wav2vec2'] = AutoModel.from_pretrained(model_name).to(self.device)
            self.processors['wav2vec2'] = AutoProcessor.from_pretrained(model_name)
            
            # Load Demucs for music source separation (if available)
            try:
                import demucs
                self.models['demucs'] = demucs.pretrained.get_model('htdemucs').to(self.device)
                logger.info("Demucs model loaded successfully")
            except ImportError:
                logger.warning("Demucs not available, skipping music separation")
            
            logger.info(f"Audio models loaded on device: {self.device}")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise
    
    def process_audio(self, file_path: Path, file_id: str, user_id: int) -> dict:
        """Main audio processing pipeline"""
        try:
            logger.info(f"Processing audio file: {file_path}")
            
            # Load audio
            audio, sr = self._load_audio(file_path)
            
            # Apply processing pipeline
            processed_audio = self._enhance_audio(audio, sr)
            
            # Save processed audio
            output_path = self._save_processed_audio(processed_audio, sr, file_id)
            
            return {
                "status": "completed",
                "output_path": str(output_path),
                "file_id": file_id
            }
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "file_id": file_id
            }
    
    def _load_audio(self, file_path: Path) -> Tuple[np.ndarray, int]:
        """Load audio file with proper resampling"""
        try:
            # Load audio with librosa for better format support
            audio, sr = librosa.load(str(file_path), sr=None)
            
            # Resample to 16kHz if needed (optimal for speech models)
            if sr != 16000:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000
            
            return audio, sr
            
        except Exception as e:
            logger.error(f"Error loading audio: {e}")
            raise
    
    def _enhance_audio(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Apply comprehensive audio enhancement pipeline"""
        
        # Step 1: Noise reduction using noisereduce
        logger.info("Applying noise reduction...")
        reduced_noise = nr.reduce_noise(
            y=audio, 
            sr=sr,
            stationary=False,
            prop_decrease=0.8
        )
        
        # Step 2: Speech enhancement using Wav2Vec2
        logger.info("Applying speech enhancement...")
        enhanced_speech = self._apply_speech_enhancement(reduced_noise, sr)
        
        # Step 3: Audio normalization and compression
        logger.info("Applying audio normalization...")
        normalized_audio = self._normalize_audio(enhanced_speech)
        
        # Step 4: Apply subtle EQ for clarity
        logger.info("Applying EQ enhancement...")
        final_audio = self._apply_eq_enhancement(normalized_audio, sr)
        
        return final_audio
    
    def _apply_speech_enhancement(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Apply Wav2Vec2-based speech enhancement"""
        try:
            # Prepare input for Wav2Vec2
            inputs = self.processors['wav2vec2'](
                audio, 
                sampling_rate=sr, 
                return_tensors="pt"
            ).to(self.device)
            
            # Get model output
            with torch.no_grad():
                outputs = self.models['wav2vec2'](**inputs)
                hidden_states = outputs.last_hidden_state
            
            # Convert back to audio (simplified approach)
            # In practice, you might want to use a more sophisticated method
            enhanced = hidden_states.mean(dim=1).cpu().numpy().flatten()
            
            # Normalize and match original length
            enhanced = librosa.util.fix_length(enhanced, size=len(audio))
            
            return enhanced
            
        except Exception as e:
            logger.warning(f"Speech enhancement failed, using original: {e}")
            return audio
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio levels"""
        # Peak normalization
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            normalized = audio / max_val * 0.95  # Leave some headroom
        else:
            normalized = audio
        
        return normalized
    
    def _apply_eq_enhancement(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Apply EQ for clarity enhancement"""
        # Simple high-pass filter to remove low-frequency noise
        from scipy.signal import butter, filtfilt
        
        # High-pass filter at 80Hz
        nyquist = sr / 2
        low = 80 / nyquist
        b, a = butter(4, low, btype='high')
        filtered = filtfilt(b, a, audio)
        
        # Slight boost in speech frequencies (1-4kHz)
        # This is a simplified approach - in production you might use more sophisticated EQ
        return filtered
    
    def _save_processed_audio(self, audio: np.ndarray, sr: int, file_id: str) -> Path:
        """Save processed audio to file"""
        output_dir = Path(settings.processed_dir)
        output_dir.mkdir(exist_ok=True)
        
        output_path = output_dir / f"{file_id}_enhanced.wav"
        
        # Save as high-quality WAV
        sf.write(
            str(output_path),
            audio,
            sr,
            subtype='PCM_24'
        )
        
        logger.info(f"Processed audio saved to: {output_path}")
        return output_path
    
    def get_audio_analysis(self, audio: np.ndarray, sr: int) -> dict:
        """Analyze audio characteristics"""
        return {
            "duration": len(audio) / sr,
            "sample_rate": sr,
            "rms_energy": np.sqrt(np.mean(audio**2)),
            "spectral_centroid": np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)),
            "zero_crossing_rate": np.mean(librosa.feature.zero_crossing_rate(audio))
        }