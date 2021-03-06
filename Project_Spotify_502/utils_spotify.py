import dotenv
import pydot
import requests
import numpy as np
import pandas as pd
import ctypes
import shutil
import multiprocessing
import multiprocessing.sharedctypes as sharedctypes
import os
import ast
import librosa
import csv
import matplotlib.image
import matplotlib.pyplot as plt
import time
from os.path import basename

# path_x = '../raw_data/fma_medium'
# path_y = '../raw_data/fma_metadata/tracks.csv'

# Number of samples per 30s audio clip.
# TODO: fix dataset to be constant.
NB_AUDIO_SAMPLES = 1321967
SAMPLING_RATE = 44100

# Load the environment from the .env file.
dotenv.load_dotenv(dotenv.find_dotenv())


class Data():

    # getting the csv absolute path
    abs_path = __file__.replace('Project_Spotify_502/utils_spotify.py', '')
    path_x_dl = os.path.join('/',abs_path, 'raw_data/fma_medium')
    path_x_dl_small = os.path.join('/',abs_path, 'raw_data/fma_small/fma_small')
    path_x_ml = os.path.join('/',abs_path, 'raw_data/fma_metadata/features.csv')
    path_y = os.path.join('/',abs_path, 'raw_data/fma_metadata/tracks.csv')
    save_path = os.path.join('/',abs_path, 'raw_data/generated_spectrograms_small')

    def __init__(self):
        return None

    def load(self, filepath):

        filename = os.path.basename(filepath)

        if 'features' in filename:
            return pd.read_csv(filepath, index_col=0, header=[0, 1, 2])

        if 'echonest' in filename:
            return pd.read_csv(filepath, index_col=0, header=[0, 1, 2])

        if 'genres' in filename:
            return pd.read_csv(filepath, index_col=0)

        if 'tracks' in filename:
            tracks = pd.read_csv(filepath, index_col=0, header=[0, 1])

            COLUMNS = [('track', 'tags'), ('album', 'tags'), ('artist', 'tags'),
                    ('track', 'genres'), ('track', 'genres_all')]
            for column in COLUMNS:
                tracks[column] = tracks[column].map(ast.literal_eval)

            COLUMNS = [('track', 'date_created'), ('track', 'date_recorded'),
                    ('album', 'date_created'), ('album', 'date_released'),
                    ('artist', 'date_created'), ('artist', 'active_year_begin'),
                    ('artist', 'active_year_end')]
            for column in COLUMNS:
                tracks[column] = pd.to_datetime(tracks[column])

            SUBSETS = pd.api.types.CategoricalDtype(categories=['small', 'medium', 'large'], ordered=True)
            tracks['set', 'subset'] = tracks['set', 'subset'].astype(SUBSETS)

            COLUMNS = [('track', 'genre_top'), ('track', 'license'),
                    ('album', 'type'), ('album', 'information'),
                    ('artist', 'bio')]
            for column in COLUMNS:
                tracks[column] = tracks[column].astype('category')

            return tracks


    def get_audio_path(self, audio_dir, track_id):
        """
        Return the path to the mp3 given the directory where the audio is stored
        and the track ID.
        Examples
        --------
        >>> import utils
        >>> AUDIO_DIR = os.environ.get('AUDIO_DIR')
        >>> utils.get_audio_path(AUDIO_DIR, 2)
        '../data/fma_small/000/000002.mp3'
        """
        tid_str = '{:06d}'.format(track_id)
        return os.path.join(audio_dir, tid_str[:3], tid_str + '.mp3')


    def generate_size(self, df, size = 'medium'):
        '''Acceptable sizes = small, medium, large'''
        return df[df['set', 'subset'] <= size]

    def generate_subset(self, df, subset = 'training'):
        '''Generates dataset corresponding to the subset indicated
        Acceptable subsets = training, validation, test'''
        return df[df['set', 'split'] == subset]

    def generate_dataset(self, path = None, size = 'medium'):
        '''Generates the whole dataset based on tracks.csv
        Acceptable sizes = small, medium, large'''

        # gets the tracks.csv path
        if path == None:
            path = self.path_y

        # generates the dataset corresponding on the size
        tracks_medium = self.generate_size(self.load(path), size = size)

        data_train = self.generate_subset(tracks_medium, subset = 'training')
        data_val = self.generate_subset(tracks_medium, subset = 'validation')
        data_test = self.generate_subset(tracks_medium, subset = 'test')

        return data_train, data_val, data_test

    def generate_y(self, path = None, size = 'medium', nb_genres = 8):
        '''Generates y (track_id and corresponding genre) based on dataset
        Acceptable sizes = small, medium, large'''

        # gets tracks.csv path
        if path == None:
            path = self.path_y

        # generates the dataset
        data_train, data_val, data_test = self.generate_dataset(path, size = size)

        y_train = data_train[('track', 'genre_top')]

        # generates list of genres based on number of tracks
        genres = list(y_train.value_counts().head(nb_genres).index)

        # filters sub_datasets
        y_train = y_train[y_train.isin(genres)]
        y_val = data_val.loc[data_val[('track', 'genre_top')].isin(genres),('track', 'genre_top')]
        y_test = data_test.loc[data_test[('track', 'genre_top')].isin(genres),('track', 'genre_top')]

        return y_train, y_val, y_test


class Data_ML(Data):

    def __init__(self):
        return None

    def get_data_numeric(self, set_size, nb_genres):
        # Load complete datasets
        tracks = self.load(self.path_y)
        features = self.load(self.path_x_ml)

        # Select columns =  set_size, set_split & target
        tracks_b = tracks[[('set', 'subset'), ('set', 'split'), ('track', 'genre_top')]]
        tracks_b.columns = tracks_b.columns.droplevel(0)

        # Select relevant set sizing
        tracks_m = tracks_b[tracks_b.subset <= set_size]

        # get top_genres
        genres = tracks_m.genre_top.value_counts().head(nb_genres).index.to_list()
        tracks_cl = tracks_m[tracks_m.genre_top.isin(genres)]

        # get split indexes
        train_index = tracks_cl[tracks_cl['split'] == 'training'].index
        val_index = tracks_cl[tracks_cl['split'] == 'validation'].index
        test_index = tracks_cl[tracks_cl['split'] == 'test'].index

        # train/val/test split
        X_train = features.loc[train_index]
        X_val = features.loc[val_index]
        X_test = features.loc[test_index]

        y_train = tracks_cl.loc[train_index, 'genre_top']
        y_val = tracks_cl.loc[val_index, 'genre_top']
        y_test = tracks_cl.loc[test_index, 'genre_top']

        return (X_train, X_val, X_test), (y_train, y_val, y_test)


class Data_DL(Data):

    def __init__(self):
        return None

    def list_of_files(self, path, directory):
        print(path)
        return [os.path.join(path, directory, file) for file in os.listdir(os.path.join(path, directory))]

    def generator_spectogram(self, filename):
        try:
            x, sr = librosa.load(filename, sr=44100, duration = 29.976598639455784, mono=True)
        except:
            return None
        stft = np.abs(librosa.stft(x, n_fft=2048, hop_length=512))
        mel = librosa.feature.melspectrogram(sr=sr, S=librosa.amplitude_to_db(stft))
        del x, stft
        return mel, sr

    def save_image(self, filename, save_path, format_):
        def scale_minmax(X, min=0.0, max=1.0):
            X_std = (X - X.min()) / (X.max() - X.min())
            X_scaled = X_std * (max - min) + min
            return X_scaled
        image_path = f'{os.path.join(save_path, filename[-10:-4])}.{format_}'
        if not os.path.exists(f'{image_path}'):
            temp = self.generator_spectogram(filename)
            if temp != None:
                mel, sr  = temp
                img = scale_minmax(mel, 0, 255).astype(np.uint8)
                img = np.flip(img, axis=0) # put low frequencies at the bottom in image
                img = 255-img # invert. make black==more energy
                if img.shape == (128,2582):
                    if format_ == 'png':
                        matplotlib.image.imsave(f'{image_path}', img, cmap='gray')
                    if format_ == 'npy':
                        img = img
                        np.save(f'{image_path}', img)
                    del temp, mel, img, sr
                    return None
                else:
                    print(f'File: {filename} is not the right size')
                    del temp, mel, img, sr
                    return filename[-10:-4]
            else:
                print(f'File: {filename} could not be loaded')
                del temp
                return filename[-10:-4]
        return None

    def save_images_dir(self, directory, y_train, y_val, y_test, format_='png', save_path=None, path_X=None):
        import warnings
        warnings.filterwarnings("ignore")
        if path_X == None:
            path_X = self.path_x_dl
        if save_path == None:
            save_path = self.save_path

        filenames = self.list_of_files(path_X, directory)
        for filename in filenames:
            temp = int(filename[-10:-4])
            subset = None
            if temp in list(y_train.index):
                subset = 'train'
                classe = y_train[temp]
            if temp in list(y_test.index):
                subset = 'test'
                classe = y_test[temp]
            if temp in list(y_val.index):
                subset = 'val'
                classe = y_val[temp]
            if subset == None:
                continue
            save_path_image = os.path.join(save_path, format_, subset, classe)
            if not os.path.exists(save_path_image):
                os.makedirs(save_path_image)
            img = self.save_image(filename, save_path_image, format_)
            if img != None:
                if subset == 'train':
                    y_train.drop(labels=temp, inplace=True)
                if subset == 'test':
                    y_test.drop(labels=temp, inplace=True)
                if subset == 'val':
                    y_val.drop(labels=temp, inplace=True)
        del subset, classe, filenames, save_path_image
        return None


    def save_images(self, path_y=None, path_X=None, format_='png', save_path=None, size = 'medium'):
        if path_X == None:
            path_X = self.path_x_dl
        if path_y == None:
            path_y = self.path_y
        if save_path == None:
            save_path = self.save_path
        y_train, y_val, y_test = self.generate_y(path_y, size = size)
        print(f'++++Successfully generated y | updated with good npy++++')

        i=0
        directories = [os.path.join(path_X, directory)[-3:] for directory in os.listdir(path_X)]
        for directory in directories:
            print(i)
            start = time.time()
            print(f'++++Starting generation of spectrograms for {directory}++++')
            self.save_images_dir(directory, y_train, y_val, y_test, format_ = format_, path_X = path_X)
            stop = time.time()
            duration = stop - start
            print(f'++++{duration} | Successfully generated spectrograms for {directory}++++')
            i=i+1
        y_train.to_csv(os.path.join(save_path, f'y_train.csv'))
        y_val.to_csv(os.path.join(save_path, f'y_val.csv'))
        y_test.to_csv(os.path.join(save_path, f'y_test.csv'))
        return None



    def generate_X(self, directory, path = None):
        if path == None:
            path = self.path_x_dl
        filenames = self.list_of_files(path, directory)
        spectrograms = []
        file_prob = []
        for filename in filenames:
            temp = self.generator_spectogram(filename)
            if temp != None:
                mel, sr  = temp
                spectrograms.append(mel)
            else:
                file_prob.append(filename)
                print(f'File: {filename} could not be loaded')
        for filename in file_prob:
            filenames.remove(filename)
        filenames = [int(filename[-10:-4].lstrip('0')) for filename in filenames]
        filenames = {track_id : index for index, track_id in enumerate(filenames)}
        return np.array(spectrograms), filenames

    def generate_X_y_subsets(self, directory, path_X = None, path_y = None):
        if path_X == None:
            path_X = self.path_x_dl
        if path_y == None:
            path_y = self.path_y
        X, filenames = self.generate_X(directory, path_X)
        y_train, y_val, y_test = self.generate_y(path_y)
        index_train = [value for key, value in filenames.items() if key in list(y_train.index)]
        index_val = [value for key, value in filenames.items() if key in list(y_val.index)]
        index_test = [value for key, value in filenames.items() if key in list(y_test.index)]
        X_train = np.array([X[i, :, :] for i in index_train])
        X_val = np.array([X[i, :, :] for i in index_val])
        X_test = np.array([X[i, :, :] for i in index_test])

        def format_y(y):
            index = [key for key, value in filenames.items() if key in list(y.index)]
            y = y[y.index.isin(index)]
            y = pd.DataFrame(y)
            y.reset_index(inplace = True)
            y.columns = [''.join(col) for col in y.columns.values]
            y.rename({'trackgenre_top' : 'genre'}, axis = 1, inplace = True)
            y['id'] = y['track_id'].map(filenames)
            y.set_index('id', inplace = True, drop = True)
            return y.sort_index()

        y_train = format_y(y_train)
        y_val = format_y(y_val)
        y_test = format_y(y_test)

        return (X_train, X_val, X_test), (y_train, y_val, y_test), filenames

    def save_X_y_dir(self, directory, save_path, path_X = None, path_y = None):
        import warnings
        warnings.filterwarnings("ignore")
        if path_X == None:
            path_X = self.path_x_dl
        if path_y == None:
            path_y = self.path_y

        X, y, filenames = self.generate_X_y_subsets(directory, path_X, path_y)
        X_train, X_val, X_test = X
        y_train, y_val, y_test = y
        np.save(os.path.join(save_path, directory, f'X_train_{directory}.npy'), X_train)
        np.save(os.path.join(save_path, directory, f'X_val_{directory}.npy'), X_val)
        np.save(os.path.join(save_path, directory, f'X_test_{directory}.npy'), X_test)

        y_val.to_csv(os.path.join(save_path, directory, f'y_val_{directory}.csv'))
        y_train.to_csv(os.path.join(save_path, directory, f'y_train_{directory}.csv'))
        y_test.to_csv(os.path.join(save_path, directory, f'y_test_{directory}.csv'))

        w = csv.writer(open(os.path.join(save_path, directory, f"filenames_{directory}.csv"), "w"))

        for key, val in filenames.items():
            w.writerow([key, val])
        return None

    def save_X_y(self, save_path, path_X = None, path_y = None):
        i=1
        if path_X == None:
            path_X = self.path_x_dl
        if path_y == None:
            path_y = self.path_y
        directories = [os.path.join(path_X, directory)[-3:] for directory in os.listdir(path_X)]
        for directory in directories:
            save_directory = os.path.join(save_path, directory)
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
                print(i)
                print(f'++++Starting generation of spectrograms for {directory}++++')
                self.save_X_y_dir(directory, save_path, path_X, path_y)
                print(f'++++Successfully generated spectrograms for {directory}++++')
                i=i+1
            else:
                print(i)
                print(f'Already loaded directory {directory}')
                i=i+1
        return None


class DataSpotify():

    abs_path = __file__.replace('Project_Spotify_502/utils_spotify.py', '')
    rawdata_path = os.path.join(abs_path, 'raw_data', 'spotify_rawdata')
    cleandata_path = os.path.join(abs_path, 'raw_data', 'spotify_dataset')

    def __init__(self):
        return None


    def merge_datasets(self, path):

        files = [f for f in os.listdir(path) if f.endswith('.csv')]

        parent_file = basename(path)

        head = [0, 1, 2] if parent_file == 'features' else 0

        # No file
        if len(files) ==0:
            return None
        """
        # only one dataset
        elif len(files) == 1:
            return pd.read_csv(os.path.join(path, files[0]), header = head)
        """

        # merge data sets
        cols = pd.read_csv(os.path.join(path, files[0]), header = head, nrows = 2).columns
        df_data = pd.DataFrame(columns = cols)

        for file in files:
            extract = pd.read_csv(os.path.join(path, file), header = head)
            df_data = pd.concat([df_data, extract])

        return df_data


    def get_clean_genre(self, path):

        import warnings
        warnings.filterwarnings("ignore")

        # extract merged datasets
        features = self.merge_datasets(os.path.join(path, 'features'))
        target = self.merge_datasets(os.path.join(path, 'metadata'))

        #drop NA + new index
        features = features.dropna().set_index(('feature', 'statistics', 'number')).rename_axis('tid')


        target = target.set_index('Unnamed: 0')[['playlist_genre']]
        target = target.rename_axis('tid').rename(columns = {'playlist_genre':'main_genre'})

        df_data = features.merge(target, how = 'inner', on = 'tid')
        df_data = df_data.groupby(df_data.index).first()

        X = df_data.drop(columns = ['main_genre'])
        y = df_data.main_genre

        return X, y



    def get_spotify_data(self):
        genres = [direct for direct in os.listdir(self.rawdata_path) if direct != ".DS_Store"]

        dic_data = {}
        min_sample = float('inf')


        for genre in genres:
            # get dict of dataset / genre
            path = os.path.join(self.rawdata_path, genre)
            X, y = self.get_clean_genre(path)

            data = X.merge(y, how='inner', on='tid')

            dic_data[genre] = data

            min_sample = min(data.shape[0], min_sample)


        return dic_data, min_sample


    def generate_spot_data(self):
        """
        if os.listdir(self.cleandata_path) != []:
            print('Please empty spotify_dataset folder before runing')
            return 'Please empty spotify_dataset folder before runing'
            """

        data, n_obs = self.get_spotify_data()
        genres = list(data.keys())

        train_set = pd.DataFrame(columns = data[genres[0]].columns)
        full_set = pd.DataFrame(columns = data[genres[0]].columns)

        for genre in genres:

            extract = data[genre].sample(n = n_obs)

            train_set = pd.concat([train_set, extract])
            full_set = pd.concat([full_set, data[genre]])


            train_set = train_set.groupby(train_set.index).first()
            full_set = full_set.groupby(full_set.index).first()

        # Save train set
        #os.makedirs(os.path.join(self.cleandata_path, 'train'))
        train_set.to_csv(os.path.join(self.cleandata_path, 'train', 'train_set.csv'), index = False)
        print('train_set saved')

        # Save full set
        #os.makedirs(os.path.join(self.cleandata_path, 'full'))
        full_set.to_csv(os.path.join(self.cleandata_path, 'full', 'full_set.csv'), index = False)
        print('full_set saved')

        return

    def get_train_set(self, balanced = True):
        subset = 'train' if balanced == True else 'full'

        path = os.path.join(self.cleandata_path, subset,f'{subset}_set.csv')
        return pd.read_csv(path)

















