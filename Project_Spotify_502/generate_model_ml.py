from Project_Spotify_502 import utils_spotify as u
from Project_Spotify_502 import trainer as tr


if __name__ == "__main__":
    print ('entering run')

    # Data loading
    data = u.DataSpotify().get_train_set(balanced = False)

    X = data.drop(columns = ['main_genre'])
    y = data.main_genre

    # Model initialization
    gen_model = tr.Trainer(X, y)
    gen_model.run(set_spot=True, model = 'xgboost')

    gen_model.save_pipe(model_name = 'model_spotify')

