import librosa
import numpy as np
import webrtcvad
import torch
import torchaudio


class SlicerVAD:
    def __init__(self,
                 sr: int,
                 min_length: int = 5000,
                 max_length: int = 15000,
                 min_interval: int = 300,
                 hop_size: int = 20, # Hop size in ms for VAD processing
                 max_sil_kept: int = 5000,
                 vad_mode: int = 3,
                 silence_db_thresh: float = -45.):
        if not min_length >= min_interval >= hop_size:
            raise ValueError('The following condition must be satisfied: min_length >= min_interval >= hop_size')
        if not max_sil_kept >= hop_size:
            raise ValueError('The following condition must be satisfied: max_sil_kept >= hop_size')
        if not max_length >= min_length:
            raise ValueError('The following condition must be satisfied: max_length >= min_length')

        self.sr = sr
        self.vad_sr = 16000 # VAD model supports only 8k, 16k, 32k, 48k
        self.vad = webrtcvad.Vad(vad_mode)
        
        # VAD processing parameters are based on vad_sr
        self.hop_length_vad = int(self.vad_sr * hop_size / 1000)
        self.min_interval_frames_vad = int(min_interval / hop_size)
        self.max_sil_kept_frames_vad = int(max_sil_kept / hop_size)
        
        # Final output length checks are based on the target sr
        self.min_length_samples = int(min_length / 1000 * self.sr)
        self.max_length_samples = int(max_length / 1000 * self.sr)
        
        self.silence_db_thresh = silence_db_thresh

    def _preprocess_audio_for_vad(self, waveform):
        """Prepares audio for VAD by resampling and ensuring it's 16-bit mono."""
        # Resample for VAD
        if self.sr != self.vad_sr:
            waveform_vad = librosa.resample(y=waveform, orig_sr=self.sr, target_sr=self.vad_sr)
        else:
            waveform_vad = waveform

        if len(waveform_vad.shape) > 1 and waveform_vad.shape[0] > 1:
            waveform_vad = librosa.to_mono(waveform_vad)
        
        if waveform_vad.dtype != np.int16:
            waveform_vad = (waveform_vad * 32767).astype(np.int16)
        
        return waveform_vad

    def slice(self, waveform):
        samples_for_vad = self._preprocess_audio_for_vad(waveform.copy())
        
        min_length_frames_vad = int(self.min_length_samples * (self.vad_sr / self.sr) / self.hop_length_vad)

        if len(waveform) < self.min_length_samples:
            return {} # Return empty if the original audio is too short

        speech_frames = []
        num_frames_vad = len(samples_for_vad) // self.hop_length_vad
        for i in range(num_frames_vad):
            start = i * self.hop_length_vad
            end = start + self.hop_length_vad
            frame = samples_for_vad[start:end]
            if len(frame) < self.hop_length_vad:
                break
            try:
                is_speech = self.vad.is_speech(frame.tobytes(), self.vad_sr)
                speech_frames.append(is_speech)
            except Exception as e:
                # This can happen if the frame is not the correct length.
                continue

        sil_tags = []
        silence_start_frame_vad = None
        clip_start_frame_vad = 0

        for i, is_speech in enumerate(speech_frames):
            if not is_speech:
                if silence_start_frame_vad is None:
                    silence_start_frame_vad = i
                continue
            
            if silence_start_frame_vad is not None:
                if i - silence_start_frame_vad >= self.min_interval_frames_vad and i - clip_start_frame_vad >= min_length_frames_vad:
                    if silence_start_frame_vad == 0:
                        end_frame = min(i, self.max_sil_kept_frames_vad)
                        sil_tags.append((0, end_frame))
                    else:
                        start_frame = max(silence_start_frame_vad, i - self.max_sil_kept_frames_vad)
                        sil_tags.append((start_frame, i))
                    
                    clip_start_frame_vad = i
                silence_start_frame_vad = None

        if silence_start_frame_vad is not None and num_frames_vad - silence_start_frame_vad >= self.min_interval_frames_vad:
            end_frame = min(num_frames_vad, silence_start_frame_vad + self.max_sil_kept_frames_vad)
            sil_tags.append((silence_start_frame_vad, end_frame))

        if not sil_tags:
             # If no silence is detected, check if the whole clip is valid
            if self.min_length_samples <= len(waveform) <= self.max_length_samples:
                rms = librosa.feature.rms(y=waveform, frame_length=512, hop_length=256)
                db = librosa.amplitude_to_db(rms, ref=1.0)
                if np.mean(db) > self.silence_db_thresh:
                    return {"0": {"slice": False, "split_time": f"0,{len(waveform)}"}}
            return {}

        chunks = []
        if sil_tags[0][0] > 0:
            start_sample = 0
            end_sample = int(sil_tags[0][0] * self.hop_length_vad * (self.sr / self.vad_sr))
            chunks.append({"slice": False, "split_time": f"{start_sample},{end_sample}"})
        
        for i in range(len(sil_tags)):
            start_sample_sil = int(sil_tags[i][0] * self.hop_length_vad * (self.sr / self.vad_sr))
            end_sample_sil = int(sil_tags[i][1] * self.hop_length_vad * (self.sr / self.vad_sr))
            chunks.append({"slice": True, "split_time": f"{start_sample_sil},{end_sample_sil}"})

            if i < len(sil_tags) - 1:
                start_sample_speech = end_sample_sil
                end_sample_speech = int(sil_tags[i+1][0] * self.hop_length_vad * (self.sr / self.vad_sr))
                chunks.append({"slice": False, "split_time": f"{start_sample_speech},{end_sample_speech}"})

        if int(sil_tags[-1][1] * self.hop_length_vad * (self.sr / self.vad_sr)) < len(waveform):
             start_sample = int(sil_tags[-1][1] * self.hop_length_vad * (self.sr / self.vad_sr))
             chunks.append({"slice": False, "split_time": f"{start_sample},{len(waveform)}"})
        
        final_chunks = []
        for chunk in chunks:
            if chunk['slice']:
                continue
            
            start_time, end_time = [int(t) for t in chunk['split_time'].split(',')]
            duration_samples = end_time - start_time

            if self.min_length_samples <= duration_samples <= self.max_length_samples:
                segment = waveform[start_time:end_time]
                if segment.size == 0:
                    continue
                rms = librosa.feature.rms(y=segment, frame_length=512, hop_length=256)
                db = librosa.amplitude_to_db(rms, ref=1.0)
                
                if np.mean(db) > self.silence_db_thresh:
                    final_chunks.append(chunk)

        if not final_chunks:
            return {}

        chunk_dict = {str(i): chunk for i, chunk in enumerate(final_chunks)}
        return chunk_dict


def cut_vad(audio_path, min_len=5000, max_len=15000, vad_mode=3, silence_db_thresh=-45., target_sr=44100, flask_mode=False, flask_sr=None):
    if not flask_mode:
        audio, sr = librosa.load(audio_path, sr=target_sr)
    else:
        audio = audio_path
        sr = flask_sr
    
    slicer = SlicerVAD(
        sr=sr,
        min_length=min_len,
        max_length=max_len,
        vad_mode=vad_mode,
        silence_db_thresh=silence_db_thresh
    )
    chunks = slicer.slice(audio)
    return chunks, audio, sr


def chunks2audio(audio, sr, chunks):
    chunks = dict(chunks)
    result = []
    for k, v in chunks.items():
        tag = v["split_time"].split(",")
        if tag[0] != tag[1]:
            # The audio passed in is already the correct, processed audio array
            result.append((v["slice"], audio[int(tag[0]):int(tag[1])]))
    return result, sr 