import os
from pydub import AudioSegment
from pydub.silence import split_on_silence
from pydub.utils import make_chunks
import shutil
import multiprocessing

def process_single_audio_file(args):
    """
    Processes a single audio file: loads, splits based on silence,
    chunks segments, and exports them.
    """
    filepath, output_dir, min_silence_len_ms, silence_thresh_dbfs, \
    keep_silence_ms, min_segment_duration_ms, max_segment_duration_ms = args

    filename = os.path.basename(filepath)
    print(f"Processing {filepath}...")
    
    try:
        audio = AudioSegment.from_wav(filepath)
    except Exception as e:
        print(f"  Error loading {filename}: {e}")
        return 0 # Return number of segments created

    # Step 1: Split on silence
    silence_based_segments = split_on_silence(
        audio,
        min_silence_len=min_silence_len_ms,
        silence_thresh=silence_thresh_dbfs,
        keep_silence=keep_silence_ms
    )

    processed_segments_for_file = []

    if not silence_based_segments:
        # print(f"  No silence-based segments found for {filename}. Processing original audio directly.")
        if len(audio) > max_segment_duration_ms:
            chunks = make_chunks(audio, max_segment_duration_ms)
            for chunk in chunks:
                if len(chunk) >= min_segment_duration_ms:
                    processed_segments_for_file.append(chunk)
                # else:
                #     print(f"  Skipping too-short chunk from non-silence split (length {len(chunk)}ms)")
        elif len(audio) >= min_segment_duration_ms:
            processed_segments_for_file.append(audio)
        # else:
        #     print(f"  Original audio {filename} is too short ({len(audio)}ms) and no silence splits, skipping.")
    else:
        for i, s_segment in enumerate(silence_based_segments):
            if len(s_segment) < min_segment_duration_ms:
                # print(f"  Silence-based segment {i} for {filename} is too short ({len(s_segment)}ms), skipping.")
                continue
            if len(s_segment) > max_segment_duration_ms:
                chunks = make_chunks(s_segment, max_segment_duration_ms)
                for chunk in chunks:
                    if len(chunk) >= min_segment_duration_ms:
                        processed_segments_for_file.append(chunk)
                    # else:
                    #     print(f"  Skipping too-short sub-chunk from segment {i} for {filename} (length {len(chunk)}ms)")
            else:
                processed_segments_for_file.append(s_segment)

    segments_created_count = 0
    for idx, segment_to_export in enumerate(processed_segments_for_file):
        output_filename = f"{os.path.splitext(filename)[0]}_seg{idx}.wav"
        try:
            segment_to_export.export(os.path.join(output_dir, output_filename), format="wav")
            # print(f"  Exported: {output_filename} (length {len(segment_to_export)}ms)")
            segments_created_count += 1
        except Exception as e:
            print(f"  Error exporting {output_filename}: {e}")
    
    print(f"  Finished processing {filename}, created {segments_created_count} segments.")
    return segments_created_count

def main_splitter():
    source = "data/dry"
    output = "data/dry-cut"
    
    MIN_SILENCE_LEN_MS = 700
    SILENCE_THRESH_DBFS = -30 # Adjusted threshold
    KEEP_SILENCE_MS = 200
    PROJECT_MIN_DURATION_MS = 2000 # 2 seconds
    USER_MAX_DURATION_MS = 30000   # 30 seconds

    print(f"Starting audio splitting from '{source}' to '{output}'...")
    print(f"Parameters:")
    print(f"  Min silence length: {MIN_SILENCE_LEN_MS}ms")
    print(f"  Silence threshold: {SILENCE_THRESH_DBFS}dBFS (Adjusted)")
    print(f"  Keep silence padding: {KEEP_SILENCE_MS}ms")
    print(f"  Min segment duration for export: {PROJECT_MIN_DURATION_MS}ms")
    print(f"  Max segment duration for export (and chunking): {USER_MAX_DURATION_MS}ms")

    if not os.path.exists(output):
        os.makedirs(output)
    else:
        print(f"Cleaning existing output directory: {output}")
        for item in os.listdir(output):
            item_path = os.path.join(output, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

    filepaths_to_process = []
    for filename in os.listdir(source):
        if filename.lower().endswith(".wav"):
            filepaths_to_process.append(os.path.join(source, filename))

    if not filepaths_to_process:
        print(f"No .wav files found in {source}. Exiting.")
        return

    # Prepare arguments for each process
    tasks_args = [
        (fp, output, MIN_SILENCE_LEN_MS, SILENCE_THRESH_DBFS, KEEP_SILENCE_MS, 
         PROJECT_MIN_DURATION_MS, USER_MAX_DURATION_MS)
        for fp in filepaths_to_process
    ]

    num_processes = multiprocessing.cpu_count()
    print(f"Using {num_processes} processes for splitting...")

    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(process_single_audio_file, tasks_args)
    
    total_segments_created = sum(results)
    print(f"\nAudio splitting finished. Processed {len(filepaths_to_process)} files.")
    print(f"Total segments created: {total_segments_created}")
    print(f"Please check the '{output}' directory for the results.")
    print("\nNext steps for you:")
    print("1. Carefully review the files in '{output}'.")
    print("2. If satisfied, clear your project\'s 'data/train/audio' and 'data/val/audio' directories (if they contain any old files).")
    print("3. Copy all .wav files from '{output}' to 'data/train/audio'.")
    print("4. Run 'python draw.py' again in your project directory (to create new validation set from these shorter clips).")
    print("5. Then, try 'python preprocess.py -c configs/reflow.yaml'.")
    print("6. If you still encounter memory issues, you might need to further reduce 'batch_size' in 'configs/reflow.yaml'.")

if __name__ == "__main__":
    main_splitter() 