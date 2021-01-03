from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import RandomForestRegressor
from cross_validation_generator import get_folds
from human_id import generate_id
import numpy as np
from sklearn.utils import shuffle
from sklearn.metrics import mean_squared_error
import pickle
from statistics import mean

CROSS_VAL = 10
LOSS = "mean_squared_error"
FEATURE_TYPE = "embeddings-ge2e"  # embeddings-ge2e, embeddings-trill, feature-streams (embeddings dir name)
FEATURE_DIR = "split-10"  # split-10, ... (subdir name in ./wavs)
METHOD = 'RF'  # KNN, RF


def predict(save_predictions=False, n_neighbors=300, max_depth=20):
    generator = get_folds(FEATURE_TYPE, FEATURE_DIR, timeseries=False, folds=CROSS_VAL, seed=21)
    run_name = generate_id(word_count=3)

    print(f"Starting run {run_name}-{METHOD} ...")

    loss_per_fold = []
    predictions = []
    truths = []

    for i in range(1, CROSS_VAL + 1):
        print('--------------------------------')
        print(f"Starting cross validation {i}/{CROSS_VAL}")
        print('--------------------------------\n')

        x_train, y_train, x_val, y_val = next(generator)

        print(f'Created folds for iteration {i}')

        x_train = np.array(x_train)
        x_val = np.array(x_val)
        y_train = np.array(y_train)
        y_val = np.array(y_val)

        x_train, y_train = shuffle(x_train, y_train)

        if METHOD == 'KNN':
            knn = KNeighborsRegressor(n_neighbors=n_neighbors)
            knn.fit(x_train, y_train)
            prediction = knn.predict(x_val)
        elif METHOD == 'RF':
            rf = RandomForestRegressor(max_depth=max_depth)
            rf.fit(x_train, y_train)
            prediction = rf.predict(x_val)

        loss = mean_squared_error(y_val, prediction)

        print(f'MSE for fold {i}: {loss}\n')

        predictions += [prediction.flatten().tolist()]
        loss_per_fold += [loss]
        truths += [y_val.flatten().tolist()]

    avg_loss = mean(loss_per_fold)
    print(f'\nMSE loss per fold: {loss_per_fold}')
    print(f"Average loss for {'k=' + str(n_neighbors) if METHOD == 'KNN' else 'max_depth=' + str(max_depth)}: {avg_loss}")

    if save_predictions:
        predictionsname = f"predictions/{FEATURE_TYPE}-{METHOD}-{avg_loss:.4f}-{run_name}.pickle"
        pickle.dump((predictions, truths), open(predictionsname, "wb"))
        print(f'Saved predictions as {predictionsname}')

    return avg_loss


def hyperparameter_search(start, end, stride):
    print(f'Hyperparameter search for {METHOD} from {start} to {end} in steps of {stride}')
    params = []
    loss_per_param = []
    for p in range(start, end+stride, stride):  # (10, 1010, 10) for k hyperparameter search from 10 to 1000 in steps of 10
        print(f'Parameter: {p}/{end}')
        avg_loss = predict(n_neighbors=p) if METHOD == 'KNN' else predict(max_depth=p)
        params += [p]
        loss_per_param += [avg_loss]
    print(params)
    print(loss_per_param)

# predict(max_depth=2)

hyperparameter_search(4, 120, 4)