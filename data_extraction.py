import os
import numpy as np
import glob
import librosa
import argparse
import pandas as pd
import concurrent.futures
import tensorflow as tf

np.set_printoptions(threshold=np.nan)

target_dict = {
    "male": 0,
    "female": 1
}


def extract_track_feature(path, index):
    print("Extracting ", path)
    y, sr = librosa.load(path)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP_LENGTH, n_mfcc=13)
    spectral_center = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=HOP_LENGTH)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=HOP_LENGTH)
    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=HOP_LENGTH)

    features = np.zeros((TIME_SERIES_LENGTH, MERGED_FEATURES_SIZE))
    features[:, 0:13] = mfcc.T[0:TIME_SERIES_LENGTH, :]
    features[:, 13:14] = spectral_center.T[0:TIME_SERIES_LENGTH, :]
    features[:, 14:26] = chroma.T[0:TIME_SERIES_LENGTH, :]
    features[:, 26:33] = spectral_contrast.T[0:TIME_SERIES_LENGTH, :]
    return (features, index)


def extract_features(base_path, track_paths, gender):
    data = np.zeros((len(track_paths), TIME_SERIES_LENGTH, MERGED_FEATURES_SIZE))
    classes = []
    futures = []
    with concurrent.futures.ProcessPoolExecutor(8) as executor:
        for i, track in enumerate(track_paths):
            classes.append(target_dict[gender[i]])
            future = executor.submit(extract_track_feature, os.path.join(base_path, track), i)
            futures.append(future)
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            data[result[1]] = result[0]

    data = tf.keras.utils.normalize(data)
    return data, np.array(classes)


def save_features(features, classes, name):
    save_features_name = "features-" + name + ".npy"
    save_classes_name = "classes-" + name + ".npy"
    with open(save_features_name, "wb") as f:
        np.save(f, features)
    with open(save_classes_name, "wb") as f:
        np.save(f, classes)


def prepare_data(csv_path, name, num_samples):
    colums = ['filename', 'gender']
    data_gender = pd.read_csv(csv_path, usecols=colums)
    data_gender = data_gender[data_gender["gender"].notnull()]
    data_gender = data_gender[data_gender["gender"] != "other"]
    tracks = data_gender['filename'].tolist()[:num_samples]
    labels = data_gender['gender'].tolist()[:num_samples]
    features, labels = extract_features(DATA_PATH, tracks, labels)
    save_features(features, labels, name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--time_series_length", type=int, default=128)
    parser.add_argument("--data")
    FLAGS, unknown = parser.parse_known_args()
    HOP_LENGTH = 128
    TIME_SERIES_LENGTH = FLAGS.time_series_length
    DATA_PATH = FLAGS.data
    MERGED_FEATURES_SIZE = 33

    print("Prepare train set")
    prepare_data(os.path.join(DATA_PATH, "cv-valid-train.csv"), "train", 500)
    print("Prepare test set")
    prepare_data(os.path.join(DATA_PATH, "cv-valid-test.csv"), "test", 50)
