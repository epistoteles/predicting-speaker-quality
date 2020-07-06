import csv
import numpy as np
import random
import os
from keras.models import Sequential
from keras.layers import Dense, Activation, Dropout
from keras.optimizers import SGD, Adam, Adamax, Adagrad, Nadam
from keras.constraints import maxnorm
import pickle
import wandb
from wandb.keras import WandbCallback

LEARNING_RATE = 0.0005
BATCH_SIZE = 50
EPOCHS = 250
OPTIMIZER = "adamax"  # sdg, adam, adamax, adagrad, nadam
ACTIVATION_FUNC = "tanh"  # tanh, sigmoid
DROPOUT_RATE = 0.4
EMBEDDING_TYPE = "embeddings"  # embeddings, embeddings-unspeech (embeddings dir name)
TRAINING_DATA = "anonymized"  # anonymized, split-10, ... (subdir name in wavs dir)
AUGMENTATION_BY_INVERSION = True  # Double the amount of data by inverting the order of each rating?
TEST_SET_MIN_SIZE = 100  # Minimum size of each test set. This will automatically be increased if augmentation is on.

wandb.init(config={"learning_rate": LEARNING_RATE,
                   "batch size": BATCH_SIZE,
                   "epochs": EPOCHS,
                   "optimizer": OPTIMIZER,
                   "activation_func": ACTIVATION_FUNC,
                   "dropout_rate": DROPOUT_RATE,
                   "embedding_type": EMBEDDING_TYPE,
                   "training_data": TRAINING_DATA,
                   "augmentation_by_inversion": AUGMENTATION_BY_INVERSION,
                   "test_set_min_size": TEST_SET_MIN_SIZE})


embeddings = []
for root, dirs, files in os.walk(os.path.join(EMBEDDING_TYPE, TRAINING_DATA)):
    for f in files:
        embeddings.append(pickle.load(open(os.path.join(root, f), 'rb')))

rankings = [96, 106, 197, 51, 190, 143, 70, 205, 143, 179, 3, 24, 108, 209, 43, 100, 144, 171, 178, 27, 2, 73, 204, 79, 73, 90, 54, 24, 96, 202, 182, 183, 224, 126, 83, 53, 214, 218, 148, 123, 189, 167, 123, 171, 17, 207, 70, 8, 193, 48, 166, 216, 193, 71, 57, 45, 210, 34, 151, 57, 82, 178, 89, 110, 32, 133, 9, 18, 120, 154, 133, 129, 32, 148, 223, 86, 119, 108, 45, 86, 100, 165, 187, 109, 141, 175, 69, 45, 150, 142, 71, 52, 23, 28, 132, 115, 213, 4, 203, 106, 84, 126, 61, 61, 113, 41, 192, 150, 140, 39, 218, 226, 140, 162, 13, 92, 191, 80, 26, 179, 160, 116, 39, 118, 127, 186, 61, 36, 167, 221, 82, 99, 192, 50, 48, 160, 151, 169, 16, 110, 45, 6, 192, 186, 105, 57, 11, 147, 63, 91, 158, 68, 155, 129, 1, 166, 109, 222, 67, 9, 134, 153, 16, 84, 96, 218, 206, 21, 58, 81, 208, 173, 178, 19, 200, 44, 125, 143, 41, 139, 169, 122, 129, 169, 203, 42, 175, 208, 179, 0, 132, 160, 78, 91, 97, 30, 89, 75, 13, 188, 29, 65, 72, 156, 12, 133, 29, 114, 27, 104, 214, 196, 212, 93, 97, 36, 9, 220, 71, 53, 22, 201, 179, 5, 141, 118, 225]
num_of_speakers = len(rankings)


def to_sparse_array(rating):
    sparse_array = [0]*num_of_speakers*2
    sparse_array[rating[0]] = 1
    sparse_array[rating[1]+num_of_speakers] = 1
    return np.array(sparse_array)


def to_two_hot_dataset(dataset):
    return np.array(list(map(lambda r: to_sparse_array(r), dataset)))


def to_two_hot_data_and_labels(dataset):
    sparse_arrays = to_two_hot_dataset(dataset)
    return sparse_arrays, np.array(dataset)[:, 2:]


def to_embedding_diff_data_and_labels(dataset):
    labels = np.array(dataset)[:, 2:3]
    embeddingsA = np.array(list(map(lambda x: embeddings[x[0]], np.array(dataset)[:, 0:1])))
    embeddingsB = np.array(list(map(lambda x: embeddings[x[0]], np.array(dataset)[:, 1:2])))
    return embeddingsA - embeddingsB, labels


def get_ranking_distance(rating):
    rank_a = rankings[rating[0]]
    rank_b = rankings[rating[1]]
    return abs(rank_a - rank_b) / num_of_speakers


def has_ranking_distance(rating, distance):
    return get_ranking_distance(rating) >= distance


def includes_external_speakers(rating, speakers, return_index=False):
    common_speakers_a = set(speakers).intersection(set(rating[:1]))
    common_speakers_b = set(speakers).intersection(set(rating[1:2]))
    if return_index:
        return bool(common_speakers_a.union(common_speakers_b)), int(bool(common_speakers_b))
    else:
        return bool(common_speakers_a.union(common_speakers_b))


def predict_based_on_ranking(rating, external_speakers=[]):
    if not external_speakers:
        return int(rankings[rating[1]] > rankings[rating[0]])
    forbidden, index = includes_external_speakers(rating, external_speakers, return_index=True)
    if not forbidden:
        return int(rankings[rating[1]] > rankings[rating[0]])
    else:
        if index == 0:
            return int(rankings[rating[1]] > num_of_speakers/2)
        if index == 1:
            return int(rankings[rating[0]] < num_of_speakers / 2)


def accuracy_based_on_ranking(dataset):
    predicted_labels = list(map(lambda r: predict_based_on_ranking(r[:2], external_speakers), dataset))
    correct_counter = 0
    for i in range(len(dataset)):
        if predicted_labels[i] == dataset[i][2]:
            correct_counter += 1
    return correct_counter / len(dataset)


with open('ratings.csv', newline='') as file:
    reader = csv.reader(file)
    data = list(reader)

data = list(map(lambda r: list(map(lambda i: int(i), r)), data))

if AUGMENTATION_BY_INVERSION:
    print("Doubling dataset size by inverting order of each rating ...")
    data_order_inverted = list(map(lambda r: [r[1], r[0], int(not r[2])], data.copy()))
    data = data + data_order_inverted
    TEST_SET_MIN_SIZE *= 2

random.shuffle(data)
print(str(len(data)) + " pairwise comparisons in total.")
test_external, external_speakers = [], []
while len(test_external) < TEST_SET_MIN_SIZE:
    external_speakers += [random.randint(0, 226) for i in range(1)]
    test_external += [x for x in data if (includes_external_speakers(x, external_speakers))]
data = [x for x in data if x not in test_external]
print("test_external:   " + str(len(test_external)))
test_naive = data[:TEST_SET_MIN_SIZE]
print("test_naive:      " + str(len(test_naive)))
test_50 = [x for x in data if (has_ranking_distance(x, 0.5))][:TEST_SET_MIN_SIZE]
print("test_50:         " + str(len(test_50)))
random.shuffle(data)
test_25 = [x for x in data if (has_ranking_distance(x, 0.25))][:TEST_SET_MIN_SIZE]
print("test_25:         " + str(len(test_25)))
train = [x for x in data if x not in (test_naive + test_50 + test_25)]
print("train:           " + str(len(train)))
print("Ratings included in test sets may overlap.")

test_sets = [test_naive, test_50, test_25, test_external]
test_set_names = ["test_naive", "test_50", "test_25", "test_external"]

print("\nPrediction accuracies based only on ranking:")
for dataset, name in zip([train] + test_sets, ["train"] + test_set_names):
    score = accuracy_based_on_ranking(dataset)
    print(f'{name + ":": <15} {score:.2f}')
    wandb.log({name + "_by_ranking": score})


# train_data, train_labels = to_two_hot_data_and_labels(train)
train_data, train_labels = to_embedding_diff_data_and_labels(train)


model = Sequential()
model.add(Dense(256, input_dim=256))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dropout(DROPOUT_RATE))
model.add(Dense(256, kernel_constraint=maxnorm(3)))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dropout(DROPOUT_RATE))
model.add(Dense(256, kernel_constraint=maxnorm(3)))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dropout(DROPOUT_RATE))
model.add(Dense(256, kernel_constraint=maxnorm(3)))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dropout(DROPOUT_RATE))
model.add(Dense(128, kernel_constraint=maxnorm(3)))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dense(64, kernel_constraint=maxnorm(3)))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dense(32))
model.add(Activation(ACTIVATION_FUNC))
model.add(Dense(1))
model.add(Activation(ACTIVATION_FUNC))

switcher = {
    "sgd": SGD(learning_rate=LEARNING_RATE),
    "adam": Adam(learning_rate=LEARNING_RATE),
    "adamax": Adamax(learning_rate=LEARNING_RATE),
    "adagrad": Adagrad(learning_rate=LEARNING_RATE),
    "nadam": Nadam(learning_rate=LEARNING_RATE)
}

model.compile(loss='binary_crossentropy', optimizer=switcher.get(OPTIMIZER), metrics=["binary_accuracy"])

model.fit(train_data, train_labels, batch_size=BATCH_SIZE, nb_epoch=EPOCHS, callbacks=[WandbCallback()])

print("\nPrediction accuracies based on embeddings:")
for test_set, name in zip(test_sets, test_set_names):
    test_data, test_labels = to_embedding_diff_data_and_labels(test_set)
    scores = model.evaluate(test_data, test_labels, verbose=0)
    print(f'{name+":": <15} {scores[1]:.2f}')
    wandb.log({name: scores[1]})
