import os
import random
import shutil

VAL_DIR = "data/val/audio"
TRAIN_DIR = "data/train/audio"
TARGET_VAL_FILES = 10
FILE_EXTENSION = ".wav"

def adjust_validation_set():
    if not os.path.exists(VAL_DIR):
        print(f"Validation directory not found: {VAL_DIR}")
        return
    if not os.path.exists(TRAIN_DIR):
        print(f"Training directory not found: {TRAIN_DIR}")
        # Optionally create it if it should exist
        # os.makedirs(TRAIN_DIR)
        return

    val_files = [f for f in os.listdir(VAL_DIR) if f.lower().endswith(FILE_EXTENSION)]
    current_val_count = len(val_files)

    print(f"Current validation files: {current_val_count}")

    if current_val_count <= TARGET_VAL_FILES:
        print(f"Validation set already has {current_val_count} files (target is {TARGET_VAL_FILES} or less). No action needed.")
        return

    num_to_move = current_val_count - TARGET_VAL_FILES
    print(f"Need to move {num_to_move} files from validation to training set.")

    random.shuffle(val_files)
    files_to_move = val_files[:num_to_move]

    moved_count = 0
    for filename in files_to_move:
        source_path = os.path.join(VAL_DIR, filename)
        destination_path = os.path.join(TRAIN_DIR, filename)
        
        # Ensure no overwrite in training set, though unlikely with unique names from draw.py
        if os.path.exists(destination_path):
            print(f"  Warning: File {filename} already exists in training set. Skipping move for this file.")
            continue
            
        try:
            shutil.move(source_path, destination_path)
            print(f"  Moved: {filename} to {TRAIN_DIR}")
            moved_count += 1
        except Exception as e:
            print(f"  Error moving {filename}: {e}")

    print(f"Successfully moved {moved_count} files.")
    final_val_count = len([f for f in os.listdir(VAL_DIR) if f.lower().endswith(FILE_EXTENSION)])
    print(f"Final validation files: {final_val_count}")

if __name__ == "__main__":
    adjust_validation_set() 