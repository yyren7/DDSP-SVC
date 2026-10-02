import os
import random
import soundfile as sf
from slicer_vad import cut_vad, chunks2audio
import argparse

def main():
    parser = argparse.ArgumentParser(description="Cut audio files using VAD.")
    parser.add_argument('--input_dir', type=str, default='data/dry', help='Input directory for audio files.')
    parser.add_argument('--output_dir', type=str, default='data/dry-cut', help='Output directory for cut audio files.')
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Find all .wav files in the input directory
    wav_files = [f for f in os.listdir(input_dir) if f.endswith('.wav')]
    
    if not wav_files:
        print(f"No .wav files found in {input_dir}")
        return

    # Process all files in the directory
    num_files_to_process = len(wav_files)
    selected_files = wav_files # Process all files
    
    print(f"Found {num_files_to_process} files to process.")
    total_segments_saved = 0

    for i, random_file in enumerate(selected_files):
        input_path = os.path.join(input_dir, random_file)
        
        print(f"\n[{i+1}/{num_files_to_process}] Processing file: {input_path}")

        try:
            # The target_sr is now hardcoded to 44100 to match the config file
            chunks, processed_audio, sr = cut_vad(input_path, target_sr=44100)
            
            if not chunks:
                print(" -> No voice segments meeting the criteria (5-15 seconds) were found.")
                continue

            results, _ = chunks2audio(processed_audio, sr, chunks)
            
            count = 0
            base_name = os.path.splitext(random_file)[0]
            
            for i, (is_slice, audio_segment) in enumerate(results):
                if not is_slice: # Only save speech segments
                    output_filename = f"{base_name}_cut_{count:03d}.wav"
                    output_path = os.path.join(output_dir, output_filename)
                    sf.write(output_path, audio_segment, sr)
                    count += 1
            
            if count > 0:
                print(f" -> Successfully saved {count} cut audio segments.")
                total_segments_saved += count
            else:
                print(" -> Found segments, but none were ultimately saved (this shouldn't happen).")


        except Exception as e:
            print(f" -> An error occurred while processing {input_path}: {e}")

    print(f"\n\nProcessing complete. Total segments saved: {total_segments_saved}")


if __name__ == '__main__':
    main() 