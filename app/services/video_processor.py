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
from moviepy.editor import VideoFileClip, AudioFileClip
from app.core.config import settings
from app.services.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() and settings.use_gpu else "cpu")
        self.audio_processor = AudioProcessor()
        self.models = {}
        self.processors = {}
        self._load_models()
    
    def _load_models(self):
        """Load AI models for video processing"""
        try:
            # Load Facebook's Wav2Vec2 model for speech enhancement
            model_name = "facebook/wav2vec2-base-960h"
            self.models['wav2vec2'] = AutoModel.from_pretrained(model_name).to(self.device)
            self.processors['wav2vec2'] = AutoProcessor.from_pretrained(model_name)
            
            logger.info(f"Video models loaded on device: {self.device}")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise
    
    def process_video(self, file_path: Path, file_id: str, user_id: int) -> dict:
        """Main video processing pipeline"""
        try:
            logger.info(f"Processing video file: {file_path}")
            
            # Extract audio from video
            audio_path = self._extract_audio(file_path, file_id)
            
            # Process the extracted audio
            audio_result = self.audio_processor.process_audio(audio_path, f"{file_id}_audio", user_id)
            
            if audio_result["status"] == "completed":
                # Recombine enhanced audio with original video
                output_path = self._recombine_video_audio(file_path, audio_result["output_path"], file_id)
                
                # Clean up temporary audio file
                audio_path.unlink(missing_ok=True)
                
                return {
                    "status": "completed",
                    "output_path": str(output_path),
                    "file_id": file_id
                }
            else:
                return audio_result
                
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "file_id": file_id
            }
    
    def _extract_audio(self, video_path: Path, file_id: str) -> Path:
        """Extract audio from video file"""
        try:
            # Create temporary directory for audio extraction
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            audio_path = temp_dir / f"{file_id}_extracted.wav"
            
            # Extract audio using moviepy
            video = VideoFileClip(str(video_path))
            audio = video.audio
            
            if audio is None:
                raise ValueError("No audio track found in video")
            
            # Write audio to file
            audio.write_audiofile(str(audio_path), verbose=False, logger=None)
            
            # Close video to free memory
            video.close()
            
            logger.info(f"Audio extracted to: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            raise
    
    def _recombine_video_audio(self, video_path: Path, enhanced_audio_path: Path, file_id: str) -> Path:
        """Recombine enhanced audio with original video"""
        try:
            output_dir = Path(settings.processed_dir)
            output_dir.mkdir(exist_ok=True)
            
            output_path = output_dir / f"{file_id}_enhanced.mp4"
            
            # Load video and enhanced audio
            video = VideoFileClip(str(video_path))
            enhanced_audio = AudioFileClip(str(enhanced_audio_path))
            
            # Set the enhanced audio as the video's audio track
            final_video = video.set_audio(enhanced_audio)
            
            # Write the final video
            final_video.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            
            # Close clips to free memory
            video.close()
            enhanced_audio.close()
            final_video.close()
            
            logger.info(f"Enhanced video saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error recombining video and audio: {e}")
            raise
    
    def get_video_analysis(self, video_path: Path) -> dict:
        """Analyze video characteristics"""
        try:
            video = VideoFileClip(str(video_path))
            
            analysis = {
                "duration": video.duration,
                "fps": video.fps,
                "size": video.size,
                "has_audio": video.audio is not None
            }
            
            if video.audio is not None:
                # Extract audio for analysis
                temp_audio_path = Path("temp_analysis.wav")
                video.audio.write_audiofile(str(temp_audio_path), verbose=False, logger=None)
                
                # Analyze audio
                audio, sr = librosa.load(str(temp_audio_path), sr=None)
                audio_analysis = self.audio_processor.get_audio_analysis(audio, sr)
                analysis["audio"] = audio_analysis
                
                # Clean up
                temp_audio_path.unlink(missing_ok=True)
            
            video.close()
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing video: {e}")
            return {"error": str(e)}