import collections
import os
import pickle
import numpy as np
from statistics import mean, stdev

from data_objects.Sample import Sample
from data_objects.Speaker import Speaker

np.set_printoptions(precision=3)

# As some speakers have spoken up to 160 articles, they would dominate some train/test sets.
# For this reason we select a maximum of MAX_PER_SPEAKER random samples per speaker.
MAX_PER_SPEAKER = 100


def get_folds(embedding_type, dataset, folds=10, seed=None):
    """
    Takes in the embedding type to use as well as the dataset to use
    and returns folds times a train set and val set with data and labels
    in the order x_train, y_train, x_val, y_val.
    """
    # set seed if given
    if seed is not None:
        np.random.seed(seed)

    # get qualities for each speaker
    speaker_to_quality_dict = pickle.load(open('speaker_to_quality_dict.pickle', 'rb'))

    samples = []

    # fill in Sample objects into lists
    for root, dirs, files in os.walk(os.path.join('wavs', dataset)):
        root_list = root.split('/')
        if len(root_list) == 4:
            _, _, speaker_name, article = root_list
            speaker_quality = speaker_to_quality_dict[speaker_name]
            if speaker_name in speaker_to_quality_dict and speaker_quality >= 0:
                speaker = Speaker(speaker_name, speaker_quality)
                for f in files:
                    if f.endswith('.wav'):
                        section = f.split('.wav')[0]
                        if embedding_type == 'embeddings-ge2e':
                            embedding = pickle.load(
                                open(os.path.join(root.replace('wavs/', f'{embedding_type}/'), f'{section}.pickle'), 'rb'))
                            samples.append(
                                Sample(speaker, article, section, embedding=embedding, embedding_type=embedding_type))
                        elif embedding_type == 'embeddings-trill':
                            embedding = pickle.load(
                                open(os.path.join(root.replace('wavs/', f'{embedding_type}/'), f'{section}.pickle'), 'rb'))
                            samples.append(
                                Sample(speaker, article, section, embedding=np.mean(embedding, axis=0), embedding_type=embedding_type))
                        else:
                            samples.append(Sample(speaker, article, section))

    # sort the used/appearing speakers by quality
    speakers_ordered_by_quality = sorted(speaker_to_quality_dict, key=speaker_to_quality_dict.get)
    print(f'number of speakers: {len(speakers_ordered_by_quality)}')
    print(f'number of speakers (without quality -1/unknown): {len(list(filter(lambda x: speaker_to_quality_dict[x] >= 0, speakers_ordered_by_quality)))}')
    print(f'amount of samples: {len(samples)}')
    print(f'unique qualities: {len(set(map(lambda x: x.speaker.quality, samples)))}')
    print(f'unique speaker names: {len(set(map(lambda x: x.speaker.name, samples)))}')
    speakers_ordered_by_quality = list(
        x for x in speakers_ordered_by_quality if x in set(map(lambda x: x.speaker.name, samples)))
    print(f'number of speakers with known quality rating and audio: {len(set(speakers_ordered_by_quality))}')
    print()

    # create 10 quantiles for the speakers by quality
    speaker_bins = np.array_split(speakers_ordered_by_quality, 20)

    # shuffle the speakers in each quantile
    for i in range(len(speaker_bins)):
        np.random.shuffle(speaker_bins[i])

    # create k empty folds
    k_folds = [[] for _ in range(folds)]

    # fill the folds iteratively with speakers from each bin
    while max(list(map(lambda x: len(x), speaker_bins))) != 0:
        for i in range(folds):
            for j in range(len(speaker_bins)):
                if len(speaker_bins[j]):
                    # this simulates list.pop()
                    random_index = np.random.randint(0, len(speaker_bins[j]))
                    k_folds[i].append(speaker_bins[j][random_index])
                    speaker_bins[j] = np.delete(speaker_bins[j], random_index)

    # print stats about the speakers in each fold
    print('Speakers in each fold:')
    print(np.array(list(map(lambda x: len(x), k_folds))))
    print('Speaker quality mean in each fold:')
    print(np.array(list(map(lambda fold: mean(list(map(lambda x: speaker_to_quality_dict[x], fold))), k_folds))))
    print(k_folds)
    print('Speaker quality std dev in each fold:')
    print(np.array(list(map(lambda fold: stdev(list(map(lambda x: speaker_to_quality_dict[x], fold))), k_folds))))

    # build x_train, y_train, x_val and y_val based on the speakers in each fold
    while folds > 0:
        folds -= 1
        train = [item for sublist in k_folds[:folds] + k_folds[folds + 1:] for item in sublist]
        val = k_folds[folds]

        # create empty result lists
        x_train, y_train, x_val, y_val = [], [], [], []

        # fill train list with up to MAX_PER_SPEAKER random samples from each speaker
        for speaker in train:
            speaker_samples = list(filter(lambda x: x.speaker.name == speaker, samples))
            for i in range(min(len(speaker_samples), MAX_PER_SPEAKER)):
                np.random.shuffle(speaker_samples)
                selected_sample = speaker_samples.pop()
                x_train += [selected_sample.embedding]
                y_train += [selected_sample.speaker.quality]

        # fill val list with up to MAX_PER_SPEAKER random samples from each speaker
        for speaker in val:
            speaker_samples = list(filter(lambda x: x.speaker.name == speaker, samples))
            for i in range(min(len(speaker_samples), MAX_PER_SPEAKER)):
                np.random.shuffle(speaker_samples)
                selected_sample = speaker_samples.pop()
                x_val += [selected_sample.embedding]
                y_val += [selected_sample.speaker.quality]

        # yield new sets for each next(generator) call
        yield x_train, y_train, x_val, y_val


def generator_test(seed):
    """Tests the function above and prints statistics"""
    # collect some stats per fold
    size_train = []
    size_val = []
    amount_speakers_train = []
    amount_speakers_val = []
    mean_embeddings_per_speaker_train = []
    mean_embeddings_per_speaker_val = []
    stdev_embeddings_per_speaker_train = []
    stdev_embeddings_per_speaker_val = []
    quality_mean_per_speaker_train = []
    quality_mean_per_speaker_val = []
    quality_mean_per_embedding_train = []
    quality_mean_per_embedding_val = []
    quality_stdev_per_speaker_train = []
    quality_stdev_per_speaker_val = []
    quality_stdev_per_embedding_train = []
    quality_stdev_per_embedding_val = []

    # create generator and get all folds produced
    generator = get_folds('embeddings-ge2e', 'split-10', 10, seed=seed)
    for _ in range(10):
        n = next(generator)
        # n[0] = train embeddings
        # n[1] = train qualities
        # n[2] = val embeddings
        # n[3] = val qualities

        # fill stats
        size_train += [len(n[0])]
        size_val += [len(n[2])]
        amount_speakers_train += [len(set(n[1]))]
        amount_speakers_val += [len(set(n[3]))]
        mean_embeddings_per_speaker_train += [mean(map(lambda x: n[1].count(x), set(n[1])))]
        mean_embeddings_per_speaker_val += [mean(map(lambda x: n[3].count(x), set(n[3])))]
        stdev_embeddings_per_speaker_train += [stdev(map(lambda x: n[1].count(x), set(n[1])))]
        stdev_embeddings_per_speaker_val += [stdev(map(lambda x: n[3].count(x), set(n[3])))]
        quality_mean_per_speaker_train += [mean(set(n[1]))]
        quality_mean_per_speaker_val += [mean(set(n[3]))]
        quality_mean_per_embedding_train += [mean(n[1])]
        quality_mean_per_embedding_val += [mean(n[3])]
        quality_stdev_per_speaker_train += [stdev(set(n[1]))]
        quality_stdev_per_speaker_val += [stdev(set(n[3]))]
        quality_stdev_per_embedding_train += [stdev(n[1])]
        quality_stdev_per_embedding_val += [stdev(n[3])]

    size_val_stdev = stdev(size_val)

    print('-------------------------')
    print(f'Results for seed {seed}:')
    print('size')
    print(size_train)
    print(size_val)
    print('amount of speakers')
    print(amount_speakers_train)
    print(amount_speakers_val)
    print('mean amount of embeddings per speaker')
    print(np.array(mean_embeddings_per_speaker_train))
    print(np.array(mean_embeddings_per_speaker_val))
    print('stdev amount of embeddings per speaker')
    print(np.array(stdev_embeddings_per_speaker_train))
    print(np.array(stdev_embeddings_per_speaker_val))
    print('mean quality per speaker')
    print(np.array(quality_mean_per_speaker_train))
    print(np.array(quality_mean_per_speaker_val))
    print('stdev quality per speaker')
    print(np.array(quality_stdev_per_speaker_train))
    print(np.array(quality_stdev_per_speaker_val))
    print('mean quality per embedding')
    print(np.array(quality_mean_per_embedding_train))
    print(np.array(quality_mean_per_embedding_val))
    print('stdev quality per embedding')
    print(np.array(quality_stdev_per_embedding_train))
    print(np.array(quality_stdev_per_embedding_val))
    print(f'Standard deviation of val sizes: {size_val_stdev}')
    print('++++++++++++++++++')

    return size_val_stdev


# print(generator_test(21))

# best_seed = 0
# lowest_stdev = 100000
#
# for i in range(1000):
#     curr_stdev = generator_test(i)
#     if curr_stdev < lowest_stdev:
#         lowest_stdev = curr_stdev
#         best_seed = i
#     print(f'currently best seed: {best_seed}')
#     print(f'currently lowest stdev: {lowest_stdev}')
